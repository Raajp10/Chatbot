# Phase 0 Research: PNW Student Knowledge Chatbot

**Feature**: 001-pnw-student-chatbot | **Date**: 2026-09-19 (re-simplified)

This revision follows a second simplification pass: reduce the design to the minimum needed to satisfy the existing functional requirements, remove fields/entities/infrastructure the project can't reliably support, and fix an inconsistency in the request-handling order. No functional requirement changed. Technology/architecture decisions only.

## 1. Application architecture: backend/frontend split

**Decision**: A FastAPI (Python) backend and a separate React (Vite) frontend, each built and run as its own Docker container (`backend`/`frontend` services in the root `docker-compose.yml`, started together via `docker compose up --build`), talking over a local REST API. There is a single deployment mode for this version — no optional build-and-serve-static-files mode.

**Rationale**: Directly required by the course constraints — FastAPI for the backend, React for the frontend, explicitly not Next.js, and (as of this revision) Docker as the standard run environment. This also cleanly separates the Python-side RAG/grounding logic (which needs the Gemini SDK, the pgvector database driver, parsing libraries) from the UI, without requiring a JS-side server runtime at all. Keeping a single "how you run this" path (`docker compose up --build`) rather than also documenting an alternate single-process static-serving mode removes a decision/config path this course project doesn't need.

**Alternatives considered**: The originally planned single Next.js app — rejected outright per course requirement #1. A Python-only server rendering HTML instead of React — rejected since the course specifically calls for React. A second "build the frontend and serve it from FastAPI" deployment mode — dropped in this revision; it added a configuration path (static file mounting, build step documentation) with no requirement driving it.

## 2. Generation model

**Decision**: Google Gemini API free tier (e.g., a `gemini-*-flash` class model) for answer generation, called from the backend via Google's `google-genai` Python SDK, prompted to answer strictly from retrieved context and to explicitly decline when context is insufficient/ambiguous/contradictory, and to state uncertainty in prose when retrieved content shows explicit signs of being outdated.

**Rationale**: Course requirement #4 explicitly disallows paid LLM APIs such as Claude and requires Google Gemini's free model API. The grounding/fail-safe prompting approach (FR-004/FR-005/FR-007) is model-agnostic and carries over unchanged from the original design.

**Alternatives considered**: Anthropic Claude API — rejected, paid API, excluded by course requirement. Other free-tier hosted LLMs — not evaluated further since the course names Gemini specifically.

**Follow-up**: Confirm the exact Gemini model name/version against current course material and Google's current free-tier offering before implementation — free-tier model availability changes over time.

## 3. Embedding model

**Decision**: Google Gemini's embedding API (e.g., an `embedding-*`/`text-embedding-*` model under the same `google-genai` SDK) as the default, matching the course's instruction to use "a free embedding API/model."

**Rationale**: Keeps the whole retrieval pipeline on one vendor/SDK (simpler dependency footprint, one API key, one rate-limit budget to manage) and satisfies the "free embedding API/model as instructed in course material" requirement.

**Alternatives considered**: A local, free, self-hosted embedding model (e.g., a small `sentence-transformers` model run on-CPU) — a reasonable fallback if the course material specifies a different embedding approach, or if Gemini's free-tier embedding quota proves too restrictive during ingestion of the sample corpus; documented here as the fallback so implementation can swap it in without a design change if needed.

**Follow-up**: Confirm the exact embedding model/approach the course material specifies; the decision above is the best default absent that detail.

## 4. Retrieval store

**Decision (revised 2026-10-02)**: PostgreSQL 17 + `pgvector`, run as a third Docker Compose service (`db`, image `pgvector/pgvector:pg17`) with a named volume (`pg_data`) so ingested content survives restarts. Two tables: `documents` (one row per approved-source manifest entry: `document_key`, `source_url`, `title`, `source_name`, `source_type`, `category`, `page_count`, `metadata` JSONB, `content_hash`, `embedding_model`, `ingested_at`) and `chunks` (one row per `SourceChunk`: `document_id`, `chunk_index`, `content`, `structure_context`, `page_number`, `metadata` JSONB holding the optional context fields from `data-model.md` plus traceability fields, `content_hash`, `embedding VECTOR(768)`), with an HNSW index on `embedding` using cosine distance. Gemini's `gemini-embedding-001` is requested at 768 dimensions because pgvector's HNSW index supports at most 2,000 (the model's default is 3,072). The backend reads `DATABASE_URL`; the schema is created idempotently by the ingestion CLI (`CREATE EXTENSION IF NOT EXISTS vector`, `CREATE TABLE IF NOT EXISTS ...`), so there is no separate migration step. Re-ingesting a source upserts its `documents` row and replaces all of its chunks in one transaction (`data-model.md`'s `SourceChunk` validation).

**Rationale**: The course's offline-RAG assignment recommends PostgreSQL + pgvector, and the project owner chose to follow it (constitution v3.0.0, Principle V). Running it from the official Docker image keeps the original objection, a native database install, from applying: `docker compose up -d db` is the only setup. pgvector also provides real SQL for inspection and verification (`SELECT COUNT(*) FROM chunks`), JSONB containment (`metadata @> ...`) for simple metadata filters, and transactional replace-on-reingest.

**Alternatives considered**: ChromaDB in embedded persistent mode (the previous decision): simpler, with no extra service, but not the course-recommended store. A raw FAISS index has no metadata filtering or persistence model. Natively installed PostgreSQL was rejected in favor of the Docker image to avoid per-machine setup.

## 5. A single persisted entity: `SourceChunk`

**Decision**: The persisted domain model is reduced to one entity, `SourceChunk` (see `data-model.md`), carrying only fields the ingestion pipeline can reliably populate from an approved source: `url`, `title`, `content`, `structureContext`, and the optional `campus`/`academicTerm`/`courseName`/`programName`/`studentLevel` attributes — each omitted, not guessed, when the source doesn't establish it. Per-turn conversational shapes (`QueryRequest`, `QueryResponse`) are transient Pydantic request/response models — not persisted at all.

Fields dropped from the earlier design, and why each is safe to drop without losing required behavior:
- `documentId` (grouping key for chunks from the same page) — nothing in the spec requires grouping chunks back into their source document at answer time; `url` alone is enough to cite and to key idempotent re-ingestion.
- `topic` (tag list) — FR-021's topic coverage is a corpus-content requirement (the approved sources must cover those topics), not something a chatbot needs to look up by tag; retrieval works by semantic similarity, not topic filtering.
- `sourceFormat` (`html`/`pdf`) — nothing in the grounding, retrieval, or generation logic branches on this after ingestion; the parser that produced a chunk already knows its own format at ingestion time and doesn't need to persist it for later use.
- `freshnessIndicator` — no persisted freshness field exists in this revision either. Explicit currency signals (a visible date, a stated academic year/term) stay in `content`/`structureContext` like the rest of a chunk's text. `backend/app/grounding.py`'s checks (tasks.md T034) instead look for explicit old-date/old-term evidence in *retrieved* chunks at query time, only when the question is time-sensitive (retrieved chunks carry an `academicTerm`, or the question matches a deadline/date topic — see tasks.md T034 for the exact heuristic): if the only relevant evidence is clearly old and no current/newer evidence also supports the answer, grounding returns `cannot_answer` (`reason = "insufficient_source_info"`); if newer evidence is also retrieved and used, the older source's uncertainty is instead surfaced in prose in the answer's `explanation` (`generation.py`). This is a check performed over retrieved content at answer time, not a derived or stored field — see `data-model.md`'s "No freshness field" note.
- `parentDocumentUrl` — existed to link a child-page/attachment chunk back to its top-level page. With the crawler replaced by an explicit approved-source manifest (§6 below), a child page or attachment is simply its own manifest entry and its own `SourceChunk` rows; nothing in the design needs to walk a parent/child relationship programmatically, since FR-011/FR-015 only require that the content be *searchable*, not that the hierarchy be reconstructed.
- `prerequisitesText` — prerequisite wording stays in `content`/`structureContext` like the rest of a catalog chunk's text; `courseName` alone is sufficient to keep it correctly attributed at answer time (FR-016 only requires correct attribution, not a separately extracted field).
- `ingestedAt` — no requirement depends on when a chunk was ingested; it isn't read by any retrieval, grounding, or clarification logic.
- The embedding vector was never a domain field — the Gemini embedding API generates it (§3) and it is stored alongside the chunk in pgvector's `chunks.embedding` column; application code only passes it through, never reasons about it.

**Rationale**: Every dropped field either duplicated information already present in `content`/`structureContext`, or existed to support a capability (topic lookup, document grouping, parent/child traversal, ingestion-time bookkeeping) that no functional requirement actually calls for. Keeping only fields the ingestion pipeline can populate from a source it's actually looking at — and never writing a placeholder value when it can't — directly follows the professor's instruction: if the data can't be reliably provided, remove the field rather than fabricate it.

**Alternatives considered**: A relational schema with `Course`/`Program` tables and foreign-key `prerequisites` relationships, plus persisted `Question`/`Answer` history — rejected as unnecessary complexity for a v1 course project with no requirement for cross-session history or complex relational joins.

## 6. Source ingestion via a curated approved-source manifest

**Decision**: Ingestion starts from a manually curated, version-controlled list of approved source URLs (a manifest — e.g., `backend/app/ingestion/sources.json` or `.yaml`), not a crawler. Each manifest entry is one approved page or PDF and always supplies `url` and `title` (both required — `title` is written by whoever curates the manifest, not scraped from the page, since not every approved source has a reliable HTML `<title>`/PDF title). A manifest entry MAY additionally carry known metadata (`campus`, `academicTerm`, `courseName`, `programName`, `studentLevel`) when that's known ahead of time from the corpus review; ingestion never infers these when the manifest doesn't supply them. When a top-level page has an important linked child page or attached document (FR-011, FR-015), that child page/document is its own explicit entry in the manifest — not discovered by following links at ingestion time. The ingestion flow is:

```
approved-source manifest → fetch/read source → HTML or PDF parser → structure-aware chunker → Gemini embedding → PostgreSQL + pgvector
```

Run offline/on-demand via a CLI entry point inside `backend/app/ingestion/`, not on the request path.

**Rationale**: A recursive crawler adds real complexity (link-following, domain allowlisting, de-duplication, failure handling for broken/unexpected links) to solve a problem the project doesn't have at this scale: the corpus is a curated set of "approved PNW sources" (FR-002/FR-004) chosen by hand during corpus review, not an open-ended site to discover. A flat, explicit list is simpler to reason about, trivially satisfies "approved sources only," and still satisfies FR-011/FR-015 as long as child pages/attachments that matter are added to the list — which corpus review would need to identify by hand either way. This is a direct application of course requirement #5 (remove unnecessary over-engineering).

**Alternatives considered**: The crawler design from the previous revision (fetch a top-level URL plus auto-discovered linked child pages/attachments, restricted to a domain allowlist) — dropped; for a "dozens to a few hundred pages" corpus (see Scale/Scope in `plan.md`), hand-curating the list is less work than building and testing crawl logic, and removes a class of bugs (crawling something unintended, missing a relevant child page a crawler's heuristics didn't catch) that a human-reviewed manifest doesn't have.

## 7. Access control

**Decision**: No authentication/SSO. The app is openly reachable. The audience disclaimer required by FR-024 is rendered statically in the React frontend (a fixed banner/text, not computed or templated per response) — it does not need to come from the API, since its content never varies per request.

**Rationale**: Directly reflects the clarification session decision; also consistent with FR-020 (no private/personalized data is ever accessed), so no security boundary is being skipped. Rendering the disclaimer as static frontend content rather than an API response field removes a field every single response previously had to carry for a value that's always the same string.

## 8. Deployment model

**Decision**: Local/self-hosted only, one mode: Docker Compose, with a `backend` service (built from `backend/Dockerfile`, running `uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port 8000` inside the container — `--no-sync` skips re-resolving dependencies at every container start, since the build already ran `uv sync`) and a `frontend` service (built from `frontend/Dockerfile`, running the Vite dev server bound to `0.0.0.0:5173`), started together via `docker compose up --build` from the repository root. No cloud hosting target, no alternate "build and serve as static files from FastAPI" mode.

**Rationale**: Directly required by the course's updated Docker requirement (course requirement #3, superseding the prior no-Docker constraint) together with requirement #2 (no paid infrastructure). Two separate services — rather than merging backend and frontend into a single container — preserves the same simple two-process architecture the project already had, just containerized: each service uses the tool suited to it (Uvicorn for FastAPI, Vite's own dev server for React) and each can be rebuilt/restarted independently. Dropping the second deployment mode (documented in a prior revision as an "optional single-process local demo") removes a configuration path — building the frontend, mounting `frontend/dist` as static files in `main.py` — that isn't needed to satisfy any requirement.

**Alternatives considered**: A single combined container running both the FastAPI server and the Vite dev server (e.g., via a process supervisor) — rejected; it would couple two independently-restartable services into one image/lifecycle for no benefit, and complicates the CORS/networking story Compose already handles cleanly with two services. Running the backend in Docker but the frontend natively via `npm run dev` — rejected as inconsistent with the course's Docker requirement, which applies to the whole system, not just the Python side.

## 9. Testing strategy

**Decision**: `pytest` with FastAPI's `TestClient` for backend unit and contract tests (retrieval logic, grounding/fail-safe logic, clarification logic, chunking, `/api/query` contract shape); React Testing Library + Vitest for frontend component tests. No browser-automation end-to-end suite, no dedicated performance-benchmark test, and no custom evaluation-runner script (see §10) — full conversational flows and the SC-001–SC-005 evaluation set are instead validated manually using `quickstart.md`.

**Rationale**: `pytest` + FastAPI's `TestClient` is the standard, low-setup way to contract-test a FastAPI app without running a live server. Dropping browser-automation e2e, a performance-benchmark harness, and a bespoke evaluation-runner script all follow the same reasoning: each is infrastructure a v1 course project doesn't need built and maintained when a documented manual procedure in `quickstart.md` covers the same ground.

**Alternatives considered**: Playwright — not required now. A CI-gated performance test or a scripted evaluation runner — dropped; see §10.

## 10. No formal performance SLO; simplified error handling

**Decision**: No formal performance SLO (e.g., a p95 latency target) is defined for v1; the project is designed for local classroom/demo use on a sample corpus, and no performance benchmark test or dedicated `quickstart.md` performance-check section exists. Error handling uses FastAPI/Pydantic's normal request validation (a `422` on a missing/empty `text` field) rather than a custom `400` response shape, and backend failures (Gemini unavailable/quota-exhausted, PostgreSQL/pgvector unreachable) are surfaced as one generic `503 Service Unavailable` with a plain `{"error": "string"}` body — no `retryAfterSeconds` field and no dedicated rate-limit-specific exception type or test, since the project can't reliably obtain or guarantee a retry-after value from the free-tier API.

**Rationale**: The original interview notes never provided a performance/scale target (see `spec.md` Assumptions) — the p95 < 10s figure in the prior revision was an invented number with no requirement behind it, existing only to justify its own benchmark test. Removing it, along with the benchmark test and its `quickstart.md` section, removes design weight with no loss of required behavior. Similarly, distinguishing a `429` rate-limit response with a machine-readable `retryAfterSeconds` from a generic `500` implies the backend can reliably extract a retry-after value from the Gemini SDK's free-tier error — not guaranteed, and not required by any FR; a single `503` with a friendly "try again shortly" message in the UI satisfies FR-007's "state the limitation" spirit without over-specifying error-handling infrastructure the project can't reliably back up.

**Alternatives considered**: Keeping the p95 target and a dedicated `Locust`/scripted benchmark — rejected as unrequired infrastructure (course requirement #5). Keeping a distinct `429` + `retryAfterSeconds` contract — rejected since it commits to a guarantee (an accurate retry time) the free-tier SDK may not reliably provide.

## 11. Success-criteria evaluation approach (SC-001–SC-005)

**Decision**: A small, curated set of representative questions (roughly 10–15) spanning the stakeholder's common-question categories (add/drop, registration, academic standing, grade appeals, financial aid deadlines, policies, procedures, contacts, at least one campus-dependent pair, and at least one prerequisite/deadline pair) is recorded as a plain table directly in `quickstart.md`, run manually against the running system, with pass/fail recorded by hand against the SC-001–SC-005 criteria. There is no separate evaluation fixture file and no runner script.

**Rationale**: SC-001–SC-005 call for evaluation against "a defined test set," but a scripted evaluation harness (a JSON fixture plus a runner that posts each question and records results) is infrastructure a course project doesn't need when the same defined set can live as a table in `quickstart.md` and be run by hand in the time it takes to ask ~10–15 questions. This is the same "keep it simple" reasoning as §9/§10, applied to evaluation specifically.

**Alternatives considered**: A `backend/tests/eval/question_set.json` fixture plus a `run_eval.py` script (the prior revision's design) — dropped; it's a small amount of extra tooling whose only job is to do what a person reading a checklist can already do for a corpus this size.

## 12. Context-dimension retrieval filtering rule (campus, program, student level, academic term)

**Decision**: One rule governs how each of the four optional context dimensions (`campus`, `programName`, `studentLevel`, `academicTerm`) restricts retrieval, applied uniformly rather than as four separately-invented filters. Once `clarification.extract_explicit_context` resolves a value for a dimension, a candidate `SourceChunk` is eligible on that dimension when any of the following holds:

1. The chunk **omits** that field entirely — a context-independent/generally-applicable source (e.g., a parking policy page that applies campus-wide, or a registration process page that doesn't vary by term). Always eligible, regardless of the resolved value.
2. The chunk's field is the literal sentinel `"both"` — defined only for `campus` and `studentLevel` (`data-model.md`). Eligible for either specific value of that dimension.
3. The chunk's field **equals the resolved value** exactly.

A chunk whose field is present and set to a *different* specific value (e.g., `campus: "hammond"` when the resolved campus is `"westville"`) is excluded — this is the "context-specific sources for one context must not mix into another's results" guarantee (FR-010, FR-013). When a dimension has **no** resolved value, no filter is applied on it at all — retrieval is not narrowed by a guess, and `clarification.find_missing_context` separately decides, from what the unfiltered retrieval actually returns, whether that dimension needs to be asked about (FR-009).

**Rationale**: The naive filter originally sketched for campus (`where={"campus": {"$in": [campus, "both"]}}`) only matches chunks that carry a `campus` key at all — a chunk that never had `campus` set (because the source doesn't distinguish by campus) has no `campus` key in its metadata, and a `$in` filter over a missing key excludes the document in most metadata stores, Chroma included. Applied literally, that filter would silently drop every context-independent source the moment any campus is resolved — directly contradicting `data-model.md`'s "omitted, never guessed" design intent for these fields, and risking `insufficient_source_info`/wrong-scope answers for perfectly good, generally-applicable sources. The 3-case rule above fixes this by treating "field absent" as its own always-eligible case, not as a value to be matched or excluded.

**Implementation approach**: Because relying on Chroma's `where` clause to correctly express "field absent OR equals X OR equals both" is fragile and Chroma-version-dependent, the simplest reliable approach is to apply this rule as a small **post-similarity-search filter in Python** (in `retrieval.py`, after Chroma returns similarity-ranked candidates), rather than pushing all four cases into the `where` clause. This avoids depending on uncertain vector-store query semantics for "missing key" matching, needs no additional service or index, and keeps the rule identical and testable across all four dimensions in one place. `tasks.md` T041 (campus), T055 (program/student-level), and T060 (academic term) implement this same rule for their respective dimension — none defines its own filtering semantics.

**Alternatives considered**: Requiring the ingestion pipeline to always write an explicit `"both"`/`"all"` sentinel instead of ever omitting a field — rejected; it would force the manifest curator to positively assert applicability for every source and dimension, reintroducing exactly the "guessed/placeholder value" problem `data-model.md` already rejects for these optional fields. Expressing the full rule as a single Chroma `where` clause (e.g., nested `$or`) — possible in principle, but its correctness depends on how a given Chroma version treats a `where` clause referencing a key some documents don't have, which is not reliably documented; the post-filter approach sidesteps that uncertainty entirely.
