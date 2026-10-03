"""Offline ingestion pipeline: fetch → parse/clean → chunk → embed → store, one source at a time."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import psycopg

from app.config import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    ConfigurationError,
    ServiceUnavailableError,
)
from app.ingestion import repository
from app.ingestion.chunker import chunk_blocks
from app.ingestion.fetch import FetchedSource, FetchError, fetch_source
from app.ingestion.models import SourceEntry
from app.ingestion.parsers import ParseError
from app.ingestion.parsers.html_parser import parse_html
from app.ingestion.parsers.pdf_parser import parse_pdf
from app.retrieval import embed_documents

EMBEDDING_MODEL_ID = f"{EMBEDDING_MODEL}@{EMBEDDING_DIMENSIONS}"

FetchFn = Callable[[str], FetchedSource]
EmbedFn = Callable[..., list[list[float]]]
LogFn = Callable[[str], None]


@dataclass(frozen=True)
class IngestResult:
    entry: SourceEntry
    status: Literal["ingested", "unchanged", "failed"]
    source_type: str | None = None
    chunk_count: int = 0
    error: str | None = None


def ingest_source(
    conn: psycopg.Connection,
    entry: SourceEntry,
    *,
    force: bool = False,
    fetch: FetchFn = fetch_source,
    embed: EmbedFn = embed_documents,
    log: LogFn = print,
) -> IngestResult:
    """Ingest one manifest entry. Raises on failure; see `ingest_all` for the per-source loop."""
    fetched = fetch(entry.url)
    log(f"  Fetched {len(fetched.content):,} bytes ({fetched.source_type})")

    if fetched.source_type == "pdf":
        parsed = parse_pdf(fetched.content, entry.url)
        log(f"  Parsed PDF: {parsed.page_count} pages, {len(parsed.text):,} characters")
    else:
        parsed = parse_html(fetched.content, entry.url)
        log(f"  Parsed webpage: {len(parsed.text):,} characters")

    chunks = chunk_blocks(parsed.blocks)
    if not chunks:
        raise ParseError(f"Parsing {entry.url} produced no chunks")
    log(f"  Created {len(chunks)} chunks")

    chunk_hashes = [hashlib.sha256(c.content.encode()).hexdigest() for c in chunks]
    content_hash = _document_hash(entry, chunks, chunk_hashes)
    existing = repository.get_document(conn, entry)
    if (
        not force
        and existing is not None
        and existing.content_hash == content_hash
        and existing.chunk_count == len(chunks)
    ):
        repository.touch_document(conn, existing.id)
        log(f"  Unchanged since last ingestion; kept {existing.chunk_count} stored chunks")
        return IngestResult(entry, "unchanged", fetched.source_type, existing.chunk_count)

    embeddings = embed([c.content for c in chunks], title=entry.title)
    log(f"  Created {len(embeddings)} embeddings ({EMBEDDING_MODEL}, {EMBEDDING_DIMENSIONS} dims)")

    repository.replace_document(
        conn,
        entry,
        source_type=fetched.source_type,
        page_count=parsed.page_count,
        content_hash=content_hash,
        embedding_model=EMBEDDING_MODEL_ID,
        chunks=chunks,
        embeddings=embeddings,
        chunk_hashes=chunk_hashes,
    )
    replaced = f" (replaced {existing.chunk_count} old chunks)" if existing else ""
    log(f"  Stored {len(chunks)} chunks{replaced}")
    return IngestResult(entry, "ingested", fetched.source_type, len(chunks))


def ingest_all(
    conn: psycopg.Connection,
    entries: list[SourceEntry],
    *,
    force: bool = False,
    fetch: FetchFn = fetch_source,
    embed: EmbedFn = embed_documents,
    log: LogFn = print,
) -> list[IngestResult]:
    """Ingest every entry; one source failing is reported and doesn't stop the others."""
    results = []
    for entry in entries:
        log(f"\nLoading {entry.title} [{entry.id}]\n  {entry.url}")
        try:
            results.append(
                ingest_source(conn, entry, force=force, fetch=fetch, embed=embed, log=log)
            )
        except ConfigurationError:
            raise  # e.g. missing GEMINI_API_KEY: every source would fail the same way
        except (FetchError, ParseError, ServiceUnavailableError, psycopg.Error) as exc:
            log(f"  FAILED: {exc}")
            results.append(IngestResult(entry, "failed", error=str(exc)))
    return results


def _document_hash(entry: SourceEntry, chunks, chunk_hashes: list[str]) -> str:
    """Changes whenever anything that ends up in the stored rows would change."""
    payload = {
        "embedding": EMBEDDING_MODEL_ID,
        "entry": [entry.id, entry.title, entry.sourceName, entry.category, entry.context],
        "chunks": [
            [h, c.structure_context, c.page_number, c.page_end]
            for c, h in zip(chunks, chunk_hashes)
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
