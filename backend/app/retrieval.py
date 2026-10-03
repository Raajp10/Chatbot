"""Gemini embeddings + pgvector similarity search over stored chunks. Implemented in T014/T015.

Query-time filtering by campus/program/student-level/academic-term (T028/T041/T055/T060) is
applied in Python after the similarity search (research.md §12) and is not implemented yet.
"""

import math
import time
from typing import Any

import psycopg
from google.genai import errors, types
from pgvector import Vector
from psycopg.types.json import Jsonb

from app.config import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    ServiceUnavailableError,
    get_client,
)
from app.db import connect

# Gemini's embed_content accepts up to 100 texts per request.
_EMBED_BATCH_SIZE = 100
_RATE_LIMIT_RETRIES = 4


def embed_text(text: str) -> list[float]:
    """Embed a student's question for similarity search."""
    return _embed([text], task_type="RETRIEVAL_QUERY")[0]


def embed_documents(texts: list[str], title: str | None = None) -> list[list[float]]:
    """Embed chunk texts for storage, batching requests. `title` is the source document's title."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[start : start + _EMBED_BATCH_SIZE]
        vectors.extend(_embed(batch, task_type="RETRIEVAL_DOCUMENT", title=title))
    return vectors


def _embed(texts: list[str], task_type: str, title: str | None = None) -> list[list[float]]:
    """Call Gemini, retrying on rate limits; raise ServiceUnavailableError on any SDK failure."""
    config = types.EmbedContentConfig(
        task_type=task_type,
        output_dimensionality=EMBEDDING_DIMENSIONS,
        title=title if task_type == "RETRIEVAL_DOCUMENT" else None,
    )
    client = get_client()
    for attempt in range(_RATE_LIMIT_RETRIES + 1):
        try:
            response = client.models.embed_content(
                model=EMBEDDING_MODEL, contents=texts, config=config
            )
            break
        except errors.APIError as exc:
            if exc.code == 429 and attempt < _RATE_LIMIT_RETRIES:
                time.sleep(2 ** (attempt + 2))  # free-tier per-minute quota: 4s, 8s, 16s, 32s
                continue
            raise ServiceUnavailableError(f"Gemini embedding request failed: {exc}") from exc
        except Exception as exc:
            raise ServiceUnavailableError(f"Gemini embedding request failed: {exc}") from exc

    vectors = [list(e.values or []) for e in response.embeddings or []]
    if len(vectors) != len(texts) or any(len(v) != EMBEDDING_DIMENSIONS for v in vectors):
        raise ServiceUnavailableError(
            f"Gemini returned {len(vectors)} embeddings for {len(texts)} texts "
            f"(expected {EMBEDDING_DIMENSIONS} dimensions each)"
        )
    # Truncated (non-3072) Gemini embeddings aren't unit-length; normalize them.
    return [_normalize(v) for v in vectors]


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector] if norm else vector


def query(
    embedding: list[float],
    where: dict[str, Any] | None = None,
    k: int = 5,
    conn: psycopg.Connection | None = None,
) -> list[dict[str, Any]]:
    """Return the `k` chunks nearest to `embedding` (cosine distance), most similar first.

    Each result is a SourceChunk-shaped dict (data-model.md): `url`, `title`, `content`,
    `structureContext`, any optional context fields the manifest supplied, plus `pageNumber`,
    `chunkIndex` and `similarity` (1 − cosine distance). `where` optionally restricts results to
    chunks whose metadata contains all the given key/value pairs.
    """
    owns_conn = conn is None
    conn = conn or connect()
    try:
        rows = conn.execute(
            """
            SELECT d.source_url, d.title, c.content, c.structure_context, c.page_number,
                   c.chunk_index, c.metadata, 1 - (c.embedding <=> %(q)s) AS similarity
            FROM chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.metadata @> %(where)s
            ORDER BY c.embedding <=> %(q)s
            LIMIT %(k)s
            """,
            {"q": Vector(embedding), "where": Jsonb(where or {}), "k": k},
        ).fetchall()
    except psycopg.Error as exc:
        raise ServiceUnavailableError(f"Vector search failed: {exc}") from exc
    finally:
        if owns_conn:
            conn.close()

    results = []
    for url, title, content, structure_context, page, index, metadata, similarity in rows:
        chunk = {key: value for key, value in (metadata or {}).items() if value is not None}
        chunk.update(url=url, title=title, content=content, chunkIndex=index,
                     similarity=float(similarity))
        if structure_context:
            chunk["structureContext"] = structure_context
        if page is not None:
            chunk["pageNumber"] = page
        results.append(chunk)
    return results


def search(question: str, k: int = 5, conn: psycopg.Connection | None = None) -> list[dict]:
    """Embed `question` and return its `k` most similar chunks."""
    return query(embed_text(question), k=k, conn=conn)
