# PNW Student Knowledge Chatbot

A chatbot that answers Purdue University Northwest (PNW) students' questions about university policies, deadlines, procedures, courses, and programs, grounded in approved PNW sources.

This is a course-project design. Design artifacts (spec, plan, research, data model, API contract, quickstart, tasks) live in [`specs/001-pnw-student-chatbot/`](specs/001-pnw-student-chatbot/).

**Stack**: FastAPI + React (Vite) + PostgreSQL/pgvector + Google Gemini (free tier). Runs via Docker Compose.

## Run it

```bash
cp backend/.env.example backend/.env   # set GEMINI_API_KEY
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- FastAPI docs: http://localhost:8000/docs

Stop with `docker compose down`. See [`specs/001-pnw-student-chatbot/quickstart.md`](specs/001-pnw-student-chatbot/quickstart.md) for validation scenarios and full setup detail.

## Offline RAG Ingestion

The offline half of RAG: a CLI pipeline that turns approved PNW webpages and PDFs into searchable, embedded chunks in PostgreSQL + pgvector. It runs on demand, not on the request path.

```text
PNW webpage / PDF   (backend/app/ingestion/sources.json)
      ↓  fetch.py         download with browser-like headers; reject errors and look-alike pages
Parser                    parsers/html_parser.py (BeautifulSoup) · parsers/pdf_parser.py (pypdf)
      ↓  cleaning.py      normalize whitespace/Unicode, drop page headers/footers
Chunker                   chunker.py — section → paragraph → sentence splitting, 15% overlap
      ↓
Embedding model           Gemini gemini-embedding-001, 768 dimensions (retrieval.py)
      ↓
PostgreSQL + pgvector     documents + chunks tables, HNSW cosine index (db.py, repository.py)
```

### Documents currently ingested

| ID | Title | Type | Source |
|---|---|---|---|
| `student-absence-policy` | Student Absence Policy | webpage | https://www.pnw.edu/dean-of-students/policies/student-absence-policy/ |
| `grade-appeal-policy` | Grade Appeal Policy | webpage | https://www.pnw.edu/dean-of-students/policies/grade-appeal-policy/ |
| `classroom-behavior-policy` | Classroom Behavior Policy | PDF (6 pages) | https://www.pnw.edu/faculty-senate/wp-content/uploads/sites/71/2021/01/Classroom-Behavior-Policy.pdf |

To add a source, add an entry to [`backend/app/ingestion/sources.json`](backend/app/ingestion/sources.json). Each entry needs `url` and `title`. `id`, `sourceName`, `category`, and the context fields `campus`, `academicTerm`, `courseName`, `programName`, and `studentLevel` are optional. Webpage vs. PDF is detected automatically.

### How it works

- **Fetching**: pnw.edu returns its generic Purdue homepage, with HTTP 200, to clients that don't look like a browser. The fetcher therefore sends normal browser headers. It also checks the response: a page whose `<link rel="canonical">` differs from the requested URL, or a `.pdf` URL that returns HTML, counts as a failed download and is never ingested silently.
- **Webpage parsing**: only the page's content container (`.main__content`, falling back to `main` / `article` / `body`) is read. Navigation, breadcrumbs, sidebars, headers, footers, cookie banners, scripts, and buttons are removed. Headings build a *heading path* for every block. Tab and accordion labels (e.g. "Grief", "Military") become sub-headings, so collapsed panel text stays attached to its label. Numbered and bulleted lists keep their numbering, and tables are flattened row by row as `Header: value; Header: value`.
- **PDF parsing**: pypdf extracts text page by page, and each block keeps its page number. Lines repeated on most pages (running headers and footers) and `Page N of M` markers are dropped. Hard-wrapped lines are rejoined into paragraphs, and short Title Case lines are detected as headings. Empty pages are skipped. There is no OCR, so a PDF with no extractable text is reported as an error.
- **Cleaning**: Unicode NFKC normalization, zero-width character removal, and collapsing of repeated spaces and newlines. Policy wording is never rewritten or summarized.
- **Chunking**: chunks are at most 2,400 characters (≈600 tokens), with 360 characters (15%) of overlap when a section is split for size. Splits happen at section headings first (once a chunk has at least 800 characters), then at paragraph and list-item boundaries, then at sentences, and at word boundaries only inside a single over-long sentence. Every chunk starts with its heading path (e.g. `Student Absence Policy > Absence Documentation Standards`), which is also stored as `structure_context`. Empty and duplicate chunks are dropped, a tiny final chunk is merged into the previous one, and the output is deterministic.
- **Embeddings**: Google Gemini `gemini-embedding-001` with `task_type=RETRIEVAL_DOCUMENT` and the document title. Requests are batched (up to 100 texts per call) and retried on rate limits. Vectors are reduced to **768 dimensions**, because pgvector's HNSW index supports at most 2,000, and then L2-normalized. Questions are embedded with `task_type=RETRIEVAL_QUERY`.
- **Storage**: PostgreSQL 17 with pgvector (Docker image `pgvector/pgvector:pg17`). The tables are created automatically on first run:
  - `documents`: `id`, `document_key` (manifest id), `source_url`, `title`, `source_name`, `source_type` (`webpage`/`pdf`), `category`, `page_count`, `metadata` JSONB, `content_hash`, `embedding_model`, `ingested_at`
  - `chunks`: `id`, `document_id` → `documents`, `chunk_index`, `content`, `structure_context`, `page_number` (PDFs), `metadata` JSONB (document id, URL, title, source type, chunk index, page range, and any manifest context fields), `content_hash`, `embedding VECTOR(768)`
  - an HNSW index on `chunks.embedding` using cosine distance

### Configuration

All settings come from environment variables. No keys are stored in the repository.

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API key ([get one free](https://aistudio.google.com/apikey)). Required. Ingestion stops with a clear message if it's missing. |
| `DATABASE_URL` | PostgreSQL URL. In `backend/.env` it's `postgresql://pnw:pnw@localhost:5433/pnw_chatbot` for host use; inside Docker, `docker-compose.yml` points it at the `db` service. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` / `POSTGRES_HOST_PORT` | Optional overrides for the `db` service (defaults `pnw` / `pnw` / `pnw_chatbot` / `5433`). |

The database is published on host port **5433**, not 5432, so it doesn't clash with a PostgreSQL install you may already have.

### Run ingestion

From the repository root:

```bash
cp backend/.env.example backend/.env        # then edit backend/.env and set GEMINI_API_KEY
docker compose up -d --build db backend     # starts PostgreSQL+pgvector (data in the pg_data volume)
docker compose exec backend uv run --no-sync python -m app.ingestion.run
```

Example output (abridged):

```text
Loading Student Absence Policy [student-absence-policy]
  Fetched 38,199 bytes (webpage)
  Parsed webpage: 4,540 characters
  Created 5 chunks
  Created 5 embeddings (gemini-embedding-001, 768 dims)
  Stored 5 chunks
...
Ingestion complete.
Database now holds 3 documents and 20 chunks.
```

Options: `--force` re-embeds every source even if unchanged; `--only <id>` ingests one source; `--manifest <path>` uses another manifest. The command exits non-zero if any source fails, and each failure is printed with its reason.

You can also run it from your host without the backend container: `docker compose up -d db`, then `cd backend && uv sync && uv run python -m app.ingestion.run`. This uses `DATABASE_URL` from `backend/.env`.

### Re-running safely (idempotency)

Re-running ingestion never duplicates data:

- Each source maps to exactly one `documents` row, keyed by its `source_url` and manifest `id`, and is upserted.
- If a source's chunks (content, structure, pages), metadata, and embedding model all hash the same as last time, it is reported as **unchanged** and skipped. This makes no Gemini calls.
- Otherwise the source is re-embedded, and its old chunks are deleted and the new ones inserted **in one transaction**. If fetching, parsing, or embedding fails, the previously stored version stays intact.

### Verify the database

```bash
# Summary: pgvector version, documents, chunks per document, missing/wrong-size embeddings
docker compose exec backend uv run --no-sync python -m app.ingestion.verify

# Similarity search (embeds the question with Gemini, returns the nearest chunks)
docker compose exec backend uv run --no-sync python -m app.ingestion.verify -k 3 \
  --query "What should a student do if they need to miss class?" \
  --query "How can a student appeal a grade?"

# Raw SQL
docker compose exec db psql -U pnw -d pnw_chatbot
```

```sql
SELECT extname FROM pg_extension WHERE extname = 'vector';
SELECT COUNT(*) FROM documents;                         -- 3
SELECT COUNT(*) FROM chunks;                            -- 20
SELECT COUNT(*) FROM chunks WHERE embedding IS NULL;    -- 0
SELECT d.title, c.chunk_index, LEFT(c.content, 150)
FROM chunks c JOIN documents d ON d.id = c.document_id
ORDER BY d.title, c.chunk_index LIMIT 10;
```

### Tests

```bash
docker compose exec backend uv run --no-sync pytest -q          # in the container
# or on the host (needs `docker compose up -d db` for the database tests):
cd backend && uv run pytest -q
```

The tests cover HTML and PDF parsing, chunk bounds, determinism and metadata, fetch error handling, the manifest, and database storage. They also verify idempotent re-ingestion, change replacement, failure isolation, and similarity search against a real pgvector database. The Gemini API is replaced by a deterministic fake embedder, so the tests use no API credits. Database tests run in a throwaway schema, so they never touch your ingested data, and they're skipped if PostgreSQL isn't running.

### Reset

`docker compose down` stops the containers and keeps the data. `docker compose down -v` also deletes the `pg_data` volume, so re-run ingestion afterwards to rebuild it.
