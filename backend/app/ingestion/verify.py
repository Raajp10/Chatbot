"""Inspect what ingestion stored, and optionally run a similarity search.

    uv run python -m app.ingestion.verify
    uv run python -m app.ingestion.verify --query "How can a student appeal a grade?" -k 3
"""

import argparse
import sys

from app.config import EMBEDDING_DIMENSIONS, ServiceUnavailableError
from app.db import connect, ensure_schema
from app.retrieval import search


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show ingested documents/chunks in pgvector")
    parser.add_argument("--query", action="append", help="question to similarity-search")
    parser.add_argument("-k", type=int, default=3, help="results per query")
    args = parser.parse_args(argv)

    try:
        with connect() as conn:
            ensure_schema(conn)
            report(conn)
            for question in args.query or []:
                print(f'\nQuery: "{question}"')
                for rank, hit in enumerate(search(question, k=args.k, conn=conn), start=1):
                    page = f", page {hit['pageNumber']}" if "pageNumber" in hit else ""
                    preview = " ".join(hit["content"].split())[:160]
                    print(f"  {rank}. [{hit['similarity']:.3f}] {hit['title']} "
                          f"(chunk {hit['chunkIndex']}{page})\n     {preview}...")
    except ServiceUnavailableError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


def report(conn) -> None:
    ext = conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()
    print(f"pgvector extension: {'v' + ext[0] if ext else 'NOT INSTALLED'}")

    rows = conn.execute(
        """
        SELECT d.document_key, d.title, d.source_type, d.ingested_at,
               count(c.id), count(c.embedding), min(vector_dims(c.embedding)),
               max(vector_dims(c.embedding)), round(avg(length(c.content)))
        FROM documents d LEFT JOIN chunks c ON c.document_id = d.id
        GROUP BY d.id ORDER BY d.title
        """
    ).fetchall()
    print(f"\nDocuments: {len(rows)}")
    for key, title, source_type, ingested_at, n, n_emb, dmin, dmax, avg_len in rows:
        dims = f"{dmin}" if dmin == dmax else f"{dmin}-{dmax}"
        print(f"  - {title} [{key}, {source_type}] {n} chunks, {n_emb} embeddings "
              f"({dims} dims), avg {avg_len} chars, ingested {ingested_at:%Y-%m-%d %H:%M:%S %Z}")

    total, missing, wrong_dims, duplicates = conn.execute(
        """
        SELECT count(*),
               count(*) FILTER (WHERE embedding IS NULL),
               count(*) FILTER (WHERE vector_dims(embedding) <> %s),
               count(*) - count(DISTINCT (document_id, content_hash))
        FROM chunks
        """,
        (EMBEDDING_DIMENSIONS,),
    ).fetchone()
    print(f"\nChunks: {total} total, {missing} missing embeddings, "
          f"{wrong_dims} with wrong dimensions, {duplicates} duplicates within a document")


if __name__ == "__main__":
    sys.exit(main())
