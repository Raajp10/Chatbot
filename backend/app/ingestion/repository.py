"""Write side of the pgvector store: one `documents` row per source, its `chunks` rows below it.

Idempotency: a document is keyed by its manifest `id` / `source_url`. Re-ingesting a source
upserts its `documents` row and, in the same transaction, deletes all of its old chunks
before inserting the new ones — so re-runs replace content and never duplicate it, and a
failure part-way leaves the previous version intact.
"""

from dataclasses import dataclass
from typing import Any

import psycopg
from pgvector import Vector
from psycopg.types.json import Jsonb

from app.ingestion.models import Chunk, SourceEntry, SourceType


@dataclass(frozen=True)
class StoredDocument:
    id: int
    content_hash: str
    embedding_model: str
    chunk_count: int


def get_document(conn: psycopg.Connection, entry: SourceEntry) -> StoredDocument | None:
    row = conn.execute(
        """
        SELECT d.id, d.content_hash, d.embedding_model,
               (SELECT count(*) FROM chunks c WHERE c.document_id = d.id)
        FROM documents d
        WHERE d.source_url = %s OR d.document_key = %s
        ORDER BY (d.source_url = %s) DESC
        LIMIT 1
        """,
        (entry.url, entry.id, entry.url),
    ).fetchone()
    return StoredDocument(*row) if row else None


def replace_document(
    conn: psycopg.Connection,
    entry: SourceEntry,
    source_type: SourceType,
    page_count: int | None,
    content_hash: str,
    embedding_model: str,
    chunks: list[Chunk],
    embeddings: list[list[float]],
    chunk_hashes: list[str],
) -> int:
    """Upsert the document and atomically replace all of its chunks. Returns the document id."""
    if not (len(chunks) == len(embeddings) == len(chunk_hashes)):
        raise ValueError("chunks, embeddings and chunk_hashes must be the same length")
    if not chunks:
        raise ValueError(f"Refusing to store {entry.url} with no chunks")

    shared_metadata = _shared_chunk_metadata(entry, source_type)
    with conn.transaction():
        # A manifest edit may change either the id or the url of an existing source; drop
        # any *other* row holding the one we're about to claim so the upsert can't conflict.
        conn.execute(
            "DELETE FROM documents WHERE document_key = %s AND source_url <> %s",
            (entry.id, entry.url),
        )
        document_id = conn.execute(
            """
            INSERT INTO documents (document_key, source_url, title, source_name, source_type,
                                   category, page_count, metadata, content_hash,
                                   embedding_model, ingested_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (source_url) DO UPDATE SET
                document_key = EXCLUDED.document_key,
                title = EXCLUDED.title,
                source_name = EXCLUDED.source_name,
                source_type = EXCLUDED.source_type,
                category = EXCLUDED.category,
                page_count = EXCLUDED.page_count,
                metadata = EXCLUDED.metadata,
                content_hash = EXCLUDED.content_hash,
                embedding_model = EXCLUDED.embedding_model,
                ingested_at = now()
            RETURNING id
            """,
            (
                entry.id, entry.url, entry.title, entry.sourceName, source_type, entry.category,
                page_count, Jsonb(entry.context), content_hash, embedding_model,
            ),
        ).fetchone()[0]
        conn.execute("DELETE FROM chunks WHERE document_id = %s", (document_id,))
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO chunks (document_id, chunk_index, content, structure_context,
                                    page_number, metadata, content_hash, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        document_id, chunk.chunk_index, chunk.content, chunk.structure_context,
                        chunk.page_number, Jsonb(_chunk_metadata(shared_metadata, chunk)),
                        chunk_hash, Vector(embedding),
                    )
                    for chunk, embedding, chunk_hash in zip(chunks, embeddings, chunk_hashes)
                ],
            )
    return document_id


def touch_document(conn: psycopg.Connection, document_id: int) -> None:
    """Record that an unchanged source was re-checked."""
    with conn.transaction():
        conn.execute("UPDATE documents SET ingested_at = now() WHERE id = %s", (document_id,))


def _shared_chunk_metadata(entry: SourceEntry, source_type: SourceType) -> dict[str, Any]:
    """Traceability fields copied onto every chunk (plus manifest context fields, if supplied)."""
    metadata: dict[str, Any] = {
        "documentId": entry.id,
        "sourceUrl": entry.url,
        "title": entry.title,
        "sourceType": source_type,
        **entry.context,
    }
    if entry.sourceName:
        metadata["sourceName"] = entry.sourceName
    if entry.category:
        metadata["category"] = entry.category
    return metadata


def _chunk_metadata(shared: dict[str, Any], chunk: Chunk) -> dict[str, Any]:
    metadata = dict(shared, chunkIndex=chunk.chunk_index)
    if chunk.page_number is not None:
        metadata["pageNumber"] = chunk.page_number
        metadata["pageEnd"] = chunk.page_end
    return metadata
