"""Ingestion CLI entrypoint. Implemented in T025/T027.

    uv run python -m app.ingestion.run [--manifest app/ingestion/sources.json] [--force] [--only ID]

Ingests every approved source in the manifest into PostgreSQL/pgvector. Safe to re-run:
unchanged sources are skipped (no new embedding calls) and changed ones have their chunks
replaced, never duplicated. `--force` re-embeds and replaces every source regardless.
Exits non-zero if any source failed.
"""

import argparse
import sys
from pathlib import Path

from app.config import ServiceUnavailableError
from app.db import connect, ensure_schema
from app.ingestion.models import load_manifest
from app.ingestion.pipeline import ingest_all

DEFAULT_MANIFEST = Path(__file__).with_name("sources.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline RAG ingestion into PostgreSQL/pgvector")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="approved-source manifest")
    parser.add_argument("--force", action="store_true", help="re-embed even unchanged sources")
    parser.add_argument("--only", action="append", metavar="ID", help="ingest only this source id")
    args = parser.parse_args(argv)

    try:
        entries = load_manifest(args.manifest)
    except (OSError, ValueError, TypeError) as exc:
        print(f"Invalid manifest {args.manifest}: {exc}", file=sys.stderr)
        return 2
    if args.only:
        unknown = set(args.only) - {e.id for e in entries}
        if unknown:
            print(f"Unknown source id(s): {sorted(unknown)}", file=sys.stderr)
            return 2
        entries = [e for e in entries if e.id in args.only]
    if not entries:
        print(f"No sources listed in {args.manifest}", file=sys.stderr)
        return 2

    print(f"Ingesting {len(entries)} source(s) from {args.manifest}")
    try:
        with connect() as conn:
            ensure_schema(conn)
            results = ingest_all(conn, entries, force=args.force)
            documents, chunks = conn.execute(
                "SELECT (SELECT count(*) FROM documents), (SELECT count(*) FROM chunks)"
            ).fetchone()
    except ServiceUnavailableError as exc:
        print(f"\nIngestion aborted: {exc}", file=sys.stderr)
        return 1

    failed = [r for r in results if r.status == "failed"]
    print("\nIngestion complete." if not failed else "\nIngestion finished with errors.")
    for r in results:
        detail = f"{r.chunk_count} chunks" if r.status != "failed" else r.error
        print(f"  [{r.status:>9}] {r.entry.id}: {detail}")
    print(f"Database now holds {documents} documents and {chunks} chunks.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
