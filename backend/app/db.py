"""PostgreSQL + pgvector connection helper and schema (documents, chunks)."""

import psycopg
from pgvector.psycopg import register_vector

from app.config import DATABASE_URL, EMBEDDING_DIMENSIONS, ServiceUnavailableError

SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS documents (
    id              BIGSERIAL PRIMARY KEY,
    document_key    TEXT NOT NULL UNIQUE,
    source_url      TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    source_name     TEXT,
    source_type     TEXT NOT NULL CHECK (source_type IN ('webpage', 'pdf')),
    category        TEXT,
    page_count      INTEGER,
    metadata        JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    content_hash    TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chunks (
    id                BIGSERIAL PRIMARY KEY,
    document_id       BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index       INTEGER NOT NULL,
    content           TEXT NOT NULL CHECK (length(btrim(content)) > 0),
    structure_context TEXT,
    page_number       INTEGER,
    metadata          JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    content_hash      TEXT NOT NULL,
    embedding         VECTOR({EMBEDDING_DIMENSIONS}) NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);
"""


def connect(dsn: str | None = None, **kwargs) -> psycopg.Connection:
    """Open an autocommit connection with the pgvector type adapter registered.

    Autocommit so that each `with conn.transaction():` block is a real, atomic transaction.
    Creates the `vector` extension first if needed, since `register_vector` requires it.
    """
    try:
        conn = psycopg.connect(dsn or DATABASE_URL, autocommit=True, **kwargs)
    except psycopg.OperationalError as exc:
        raise ServiceUnavailableError(
            f"Could not connect to PostgreSQL at {_redact(dsn or DATABASE_URL)}. "
            "Is the database running? Start it with `docker compose up -d db`.\n"
            f"Details: {exc}"
        ) from exc
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    return conn


def ensure_schema(conn: psycopg.Connection) -> None:
    """Create the documents/chunks tables and vector index if they don't exist (idempotent)."""
    with conn.transaction():
        conn.execute(SCHEMA_SQL)
    row = conn.execute(
        """
        SELECT format_type(atttypid, atttypmod)
        FROM pg_attribute
        WHERE attrelid = 'chunks'::regclass AND attname = 'embedding'
        """
    ).fetchone()
    expected = f"vector({EMBEDDING_DIMENSIONS})"
    if row and row[0] != expected:
        raise ServiceUnavailableError(
            f"chunks.embedding is {row[0]} but the configured embedding model produces "
            f"{expected}. Drop the old tables (e.g. `docker compose down -v`) and re-run ingestion."
        )


def _redact(dsn: str) -> str:
    """Hide the password in a postgresql:// URL for error messages."""
    if "@" not in dsn or "://" not in dsn:
        return dsn
    scheme, rest = dsn.split("://", 1)
    creds, host = rest.rsplit("@", 1)
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"
