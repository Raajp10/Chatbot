---
description: "Task list for feature implementation"
---

# Tasks: PNW Student Knowledge Chatbot

**Input**: Design documents from `/specs/001-pnw-student-chatbot/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/query-api.md, quickstart.md

**Tests**: Included. `contracts/query-api.md` explicitly lists a "Contract test coverage" section for this command to schedule, and `.specify/memory/constitution.md`'s Development Workflow principle requires automated tests for any change to grounding, fail-safe, clarification, or retrieval behavior.

**Organization**: Tasks are grouped by user story (from spec.md, in priority order P1 → P1 → P2 → P2 → P3) to enable independent implementation and testing of each story.

**Re-simplification note (2026-09-19)**: This task list was renumbered from scratch after a data-model/design simplification pass (see `research.md`, `data-model.md`, `plan.md`). Tasks for the recursive crawler, removed `Source` fields, `StructuredFact`/`deadlinesOrConditions`, the API-provided disclaimer, `contactInfo`, the performance benchmark, the custom evaluation runner, optional static-frontend serving, and rate-limit-specific machinery have been removed outright rather than replaced. No functional requirement was dropped — see plan.md's Constitution Check.

**Consistency-cleanup note (2026-09-19, later pass)**: No task IDs were added, removed, or renumbered in this pass. `clarification.py` (T040/T053/T060) was clarified to own exactly two functions — `extract_explicit_context` and `find_missing_context` — invoked at two different points in T020's orchestration order, which was corrected so explicit context is extracted *before* retrieval and the missing-context check runs *after* retrieval (previously retrieval ran before any context extraction). `grounding.py`'s conflicting-source check (T034) now always resolves a material conflict to `cannot_answer`, never an `answered` response with an explanation. The approved-source manifest's required fields grew to include `title` (T025/T026). `academicTerm` retrieval filtering was added to T060.

**`/speckit-analyze` remediation note (2026-09-19)**: No task IDs added/removed/renumbered here either — all fixes are description edits. T059 was re-scoped from parser-level (duplicating T023) to chunker-level row-boundary work. T051 was narrowed to `courseName`-only raw-text boosting, decoupled from `extract_explicit_context`/T055's `programName` handling (T020 step 4 and T028 updated to match). T034 now defines "material conflict" and "time-sensitive" instead of leaving them as unoperationalized terms. T022 gained a second test for the child-page/attachment combination case (FR-011/US1 AC2), previously only covered manually. T029/data-model.md's `explanation` note now address the multi-sub-topic edge case. `.specify/memory/constitution.md` Principle II was amended (1.0.0 → 1.0.1, PATCH) to state the FR-018 current-evidence exception explicitly.

**Docker migration note (2026-09-21)**: The course now requires Docker (`.specify/memory/constitution.md` Principle V amended 1.0.1 → 2.0.0, MAJOR — see its Sync Impact Report), reversing the prior no-Docker constraint. Docker Compose setup tasks (Dockerfiles, `.dockerignore`s, `docker-compose.yml`) are integrated sequentially into Phase 1 as **T008–T011**. No existing task's description changed in a way that alters its behavior, only mentions of "no Docker"/local-only execution paths (T007's `.gitignore` entries, T013/T015's Chroma-path wording, T067's README note, the Notes section) were updated to match. No functional requirement, entity, or contract changed.

**Renumbering note (2026-09-21)**: All task IDs were renumbered to run sequentially T001–T067 with no gaps (the Docker tasks above were previously appended as T064–T067 to avoid an earlier renumbering pass; they and every task from the old T008 onward have now been shifted into sequential order). Every cross-reference to a task ID, in this file and in `plan.md`/`research.md`/`data-model.md`, was updated to match. No task content, ordering of work, `[x]`/`[ ]` status, requirement, or architectural/implementation decision changed — only the ID numbers and the references to them.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Paths follow the backend/ (FastAPI) + frontend/ (React/Vite) structure in plan.md — run via Docker Compose (backend/Dockerfile, frontend/Dockerfile, root docker-compose.yml), no Next.js, local ChromaDB persisted via a Docker volume, Google Gemini free-tier APIs, one deployment mode

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure, per plan.md's Project Structure section

- [x] T001 Create the `backend/` and `frontend/` directory skeletons matching the Project Structure in `specs/001-pnw-student-chatbot/plan.md` — all directories now exist with placeholder files (docstring-only `.py` stubs, comment-only `.jsx`/`.js` stubs, `sources.json` as `[]`); no real logic written into any of them — that remains each file's own specific task (T012–T064) to implement
- [x] T002 Initialize the backend Python project: `backend/pyproject.toml` managed with `uv`, adding `fastapi`, `uvicorn[standard]`, `chromadb`, `google-genai`, `beautifulsoup4`, `pypdf`, `pydantic`, `pytest`, `httpx` as dependencies — done; `pytest`/`httpx` (plus `ruff`) live in a `[dependency-groups] dev` group, installed by `uv sync` (T008) rather than as plain `dependencies`, satisfying the same "these packages are available" intent
- [x] T003 [P] Initialize the frontend React project: `frontend/package.json` via a Vite React template (`npm create vite@latest frontend -- --template react`), no extra dependencies beyond the Vite/React defaults — done; hand-written rather than scaffolded via the `npm create vite` CLI, but the resulting `package.json`/`vite.config.js`/`index.html`/`src/main.jsx`/`src/App.jsx` match the standard Vite React template shape with only `react`, `react-dom`, `vite`, `@vitejs/plugin-react` as dependencies, and the built image serves the page (validated)
- [x] T004 [P] Configure backend linting/formatting: add a `ruff` configuration section to `backend/pyproject.toml`
- [x] T005 [P] Configure frontend linting/formatting: add an ESLint config at `frontend/eslint.config.js` — flat config (ESLint 8.57, which supports it natively) with `@eslint/js` recommended, `eslint-plugin-react` (`jsx-uses-react`/`jsx-uses-vars`, needed because plain `no-unused-vars` doesn't otherwise recognize a component referenced only via a JSX tag), `eslint-plugin-react-hooks` recommended, and `eslint-plugin-react-refresh`; `npm run lint` added to `package.json` and validated clean (0 errors) inside the built container
- [x] T006 Create `backend/.env.example` documenting `GEMINI_API_KEY=your-key-here` (per research.md §2/§3 — no other API keys needed, no paid services)
- [x] T007 [P] Add `.gitignore` entries for `backend/data/chroma/`, `backend/.env`, `frontend/node_modules/`, and `frontend/dist/` — verified with `git check-ignore -v` against all four paths
- [x] T008 [P] Create `backend/Dockerfile`: `python:3.12-slim` base image, install `uv`, `COPY pyproject.toml` and run `uv sync` (the full dependency set, including the `dev` group — `pytest`/`httpx`/`ruff` — so the one image can also run tests; no separate test/dev image, per the Simplicity principle), then `COPY . .` (brings in `app/` and `tests/` together, so test files are present in the image once they exist — `backend/.dockerignore`, T011, deliberately does NOT exclude `tests/`), `EXPOSE 8000`, and run `uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port 8000` as the container command (`--no-sync` skips re-resolving/downloading dependencies at every container start, since `uv sync` already populated `.venv` at build time) (per research.md §8, §9)
- [x] T009 [P] Create `frontend/Dockerfile`: `node:22` base image, `COPY package.json` and run `npm install`, then `COPY . .`, `EXPOSE 5173`, and run the Vite dev server bound to `0.0.0.0:5173` as the container command (per research.md §8); `frontend/vite.config.js`'s `server.host` MUST be set to `0.0.0.0` so the dev server accepts connections from outside the container
- [x] T010 Create the root `docker-compose.yml` with a `backend` service (build context `./backend`, `env_file: backend/.env` for `GEMINI_API_KEY` — never hard-coded, `environment: CHROMA_PATH=/app/data/chroma`, a named volume `chroma_data` mounted at `/app/data/chroma` for persistence across restarts, port `8000:8000`) and a `frontend` service (build context `./frontend`, `depends_on: backend`, port `5173:5173`); this is the file `docker compose up --build` reads (per research.md §1, §8)
- [x] T011 [P] Add `backend/.dockerignore` (`.venv`, `__pycache__`, `*.pyc`, `.env`, `data/chroma`, `.git`, `.ruff_cache`, `.pytest_cache` — deliberately NOT `tests`, since T008's image needs `tests/` present to run pytest inside the container) and `frontend/.dockerignore` (`node_modules`, `dist`, `.git`) so build contexts stay small, local secrets/venvs/caches are never copied into an image, and tests remain runnable in the built image

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T012 Define the Pydantic request/response models in `backend/app/models.py`, exactly as shaped in `contracts/query-api.md` and `data-model.md`: `QueryRequest` (`text: str` with a field constraint enforcing non-empty-after-trim, `context: {campus: Literal["hammond","westville"] | None, academicTerm: str | None, program: str | None, studentLevel: Literal["undergraduate","graduate"] | None}`) and the three `QueryResponse` variants discriminated by `type` — `answered` (`directAnswer`, `explanation`, `sources: list[{title: str, url: str}]` non-empty), `clarification_needed` (`promptText`, `missingContext: Literal["campus","program","academic_term","student_level"]`, `options: list[str] | None`), `cannot_answer` (`message`, `reason: Literal[...]`, `officeName: str` non-empty) — done; a Pydantic v2 discriminated union on `type` (`Annotated[AnsweredResponse | ClarificationNeededResponse | CannotAnswerResponse, Field(discriminator="type")]`); `text`/`officeName` non-emptiness-after-trim uses `StringConstraints(strip_whitespace=True, min_length=1)` (a standard field constraint, per the contract's wording) and `sources` non-emptiness uses `Field(min_length=1)`; verified with a `TypeAdapter` inside the built container (valid/invalid payloads for all three variants, plus request-text trimming)
- [x] T013 Implement the backend config loader in `backend/app/config.py`, reading `GEMINI_API_KEY` and a `CHROMA_PATH` (default `/app/data/chroma` — matching the path `docker-compose.yml` sets via `environment: CHROMA_PATH=/app/data/chroma` and the `chroma_data` volume mounts to, T010; research.md §4) from the environment via `.env`, and exposing a single configured Gemini SDK client for `retrieval.py`/`generation.py`/`ingestion/` to share — done; reads `os.environ` directly (Compose's `env_file: backend/.env`, T010, already populates the container's environment, so no `python-dotenv` dependency is needed) and exposes a lazily-constructed shared `genai.Client()` via `get_client()`; `ServiceUnavailableError` also lives here since generation.py/retrieval.py/main.py all already import this module
- [x] T014 Implement Gemini call helpers using the `google-genai` SDK (per research.md §2/§3): a `generate_text(prompt)` helper in `backend/app/generation.py` and an `embed_text(text)` helper in `backend/app/retrieval.py` (reused by `ingestion/run.py` for chunk embedding); any SDK-level failure (quota, unavailability) raises a single `ServiceUnavailableError` — done; both wrap `client.models.generate_content`/`client.models.embed_content` in `try/except Exception`, re-raising as `ServiceUnavailableError`; verified live against the real Gemini API inside the built container — the placeholder key in `backend/.env` correctly produced a `400 INVALID_ARGUMENT` from the SDK that was correctly wrapped into `ServiceUnavailableError` (a real key is needed for a successful generation/embedding call, but the wrapping behavior this task specifies is confirmed)
- [x] T015 Implement the Chroma store wrapper in `backend/app/retrieval.py`: `get_or_create_collection()`, `add_chunks(chunks)` (each chunk assigned its own internal Chroma document ID derived from `url` + chunk index, e.g. `f"{url}#{i}"` — never the bare `url` shared across a source's chunks), `delete_chunks_for_url(url)` (removes any chunks already stored for a `url`, used by ingestion to re-ingest idempotently), and `query(embedding, where=None, k=5)`, using Chroma's local `PersistentClient` pointed at `CHROMA_PATH` (per research.md §4 — an embedded store, no separate Chroma server process/container; runs inside the `backend` container with `CHROMA_PATH=/app/data/chroma` mounted to the `chroma_data` Docker volume, T010, for persistence); Chroma's own document ID is treated purely as an implementation detail of this wrapper, not a domain field — done; verified live inside the built container: two chunks sharing one `url` were assigned distinct IDs (collection count reached 2, not 1), optional metadata fields were correctly omitted rather than null when a chunk didn't supply them, `query()` returned chunks with `content` merged back in, and `delete_chunks_for_url()` removed both of that url's chunks (count back to 0)
- [x] T016 Implement the FastAPI app entrypoint in `backend/app/main.py`: create the `FastAPI()` instance, enable CORS for the frontend dev origin (`http://localhost:5173`), and mount a stub `POST /api/query` router (no `/health` route — not required for this local course project) — done; `app.include_router(query_router)` mounts `backend/app/api/query.py`'s stub route; the placeholder `GET /` root left over from T001's scaffold was removed, since the contract defines `POST /api/query` as the only external-facing route and nothing else depended on `GET /`
- [x] T017 [P] Implement global error handling in `backend/app/main.py`: a `ServiceUnavailableError` handler returning `503` with body `{"error": str}`, per `contracts/query-api.md` — `422` validation responses are FastAPI/Pydantic's default behavior and need no custom handler — done; `@app.exception_handler(ServiceUnavailableError)` returns `JSONResponse(status_code=503, content={"error": str(exc)})`; verified in isolation with `TestClient` (a route raising `ServiceUnavailableError` correctly returned `503` with the expected body) since the live `/api/query` route doesn't call Gemini yet (that wiring starts at T030)
- [x] T018 [P] Implement the frontend API client wrapper in `frontend/src/api/query.js`: `postQuery({ text, context })` → `fetch("http://localhost:8000/api/query", { method: "POST", ... })`, parsing the JSON response per `contracts/query-api.md`; `context` MUST support all four fields (`campus`, `academicTerm`, `program`, `studentLevel`) so any clarification type can be answered on the next call — done; passes `context` through untouched (caller controls its shape, so all four fields are supported), throws an `Error` using the response body's `error` field on a non-2xx response
- [x] T019 [P] Implement the base chat UI shell in `frontend/src/App.jsx` and `frontend/src/components/DisclaimerBanner.jsx`: render a static, hardcoded disclaimer string ("This tool is intended for currently registered PNW undergraduate and graduate students...") — not sourced from the API response — plus a basic message input and message list, with no story-specific result rendering yet — done; `DisclaimerBanner.jsx` renders the fixed string as a module-level constant; `App.jsx` adds a controlled text input + submit handler calling `postQuery`, and a message list that dumps the raw JSON response for assistant turns (deliberately not using `AnswerMessage`/`ClarificationPrompt`/`ReferralMessage` — those are US1/US2/US3 tasks); verified `npm run lint` passes and the Vite dev server serves the page (HTTP 200) inside the built container
- [x] T020 Define the single authoritative end-to-end orchestration order for `POST /api/query` in `backend/app/api/query.py` (e.g., as a top-level docstring on the handler plus a sequence of clearly named internal calls). This is the one place that owns call order; every task that adds a piece of the pipeline (T030, T035, T042, T054, T061) implements its own logic into this order and MUST NOT define a conflicting order of its own. `clarification.py` (T040/T053/T060) owns exactly two functions used at two different points below: `extract_explicit_context(question_text, request_context)` and `find_missing_context(retrieved_chunks, resolved_context)` — it is still one module, not two. The order — matching the Architecture diagram in `plan.md` — is:
  1. Validate the request (T012's Pydantic validation; a `422` is returned automatically on failure).
  2. Run the private-data/personalized-records check (`grounding.py`, T034). If triggered, return `cannot_answer` with `officeName` set WITHOUT calling retrieval.
  3. Call `clarification.extract_explicit_context(text, context)` to resolve as much of campus/program/student_level/academic_term as possible from the request's `context` and/or explicit mentions in the question text. This does not yet decide whether anything is missing — only what's already resolvable.
  4. Retrieve relevant `SourceChunk`s (T028), applying: (i) whatever resolved-context metadata filters (T041 campus, T055 program/student-level, T060 academic-term) step 3 supports, and (ii) independently of step 3, T051's raw-text `courseName` boost whenever the question names a specific course.
  5. Call `clarification.find_missing_context(retrieved_chunks, resolved_context)` to check, using the chunks actually retrieved, whether campus/program/student_level/academic_term is still required and unresolved — checked in this priority order when more than one could apply: (a) campus, (b) program, (c) student_level, (d) academic_term.
  6. If context is still missing, return exactly one `clarification_needed` response for the first applicable item in that priority order — do not proceed further.
  7. Otherwise, run the grounding/fail-safe checks (`grounding.py`, T034): (a) insufficient grounding, (b) a *material* conflict between retrieved sources on the fact needed to answer — this ALWAYS returns `cannot_answer` (`reason = "conflicting_sources"`); generation is never called to pick a side, (c) out-of-scope, (d) explicit-outdated-evidence for time-sensitive questions (flags `insufficient_source_info` only when no current/newer evidence also supports the answer — no persisted freshness field is involved). If any check fails, return `cannot_answer` with `officeName` set — do not proceed further.
  8. Otherwise, call grounded Gemini generation (T029).
  9. Validate that the `answered` result has non-empty `sources` before returning (data-model.md validation).
  10. Return the final response.

  **Implementation note**: done — the 10-step order above is reproduced verbatim as the `query()` route handler's docstring in `backend/app/api/query.py`, which also mounts the `POST /api/query` route (T016) via an `APIRouter`. Since `grounding.py`/`clarification.py` and retrieval/generation wiring don't exist until later user-story tasks, the handler body itself is a stub (`raise NotImplementedError(...)`) — verified live: a well-formed request returns `500` (the stub firing as expected), while an empty/missing `text` correctly short-circuits to `422` via T012's Pydantic validation before the handler ever runs.

**Checkpoint**: Foundation ready — user story implementation can now begin. T020's authoritative orchestration order is now defined; every later task that touches `query.py` implements into that order rather than defining its own.

---

## Phase 3: User Story 1 - Get a Direct, Grounded Answer to a University Question (Priority: P1) 🎯 MVP

**Goal**: A student asks a plain-language university question; the chatbot searches the approved PNW corpus and returns a direct answer, a plain-language explanation, and the official source(s) that support it — including cases where the answer requires combining a top-level page with a linked child page or attached document.

**Independent Test**: Ingest the sample corpus (per `quickstart.md`) and submit representative questions from the stakeholder's common-question list (e.g., "How do I pay a parking ticket?"). Confirm each `answered` result is direct, understandable, and cites a specific approved source; confirm a question requiring a linked child page reflects the combined content.

### Tests for User Story 1

- [ ] T021 [P] [US1] Contract test: `POST /api/query` returns `type == "answered"` with a non-empty `sources` list (each with `title`/`url`) for a question fully covered by the sample corpus, in `backend/tests/contract/test_query_answered.py`
- [ ] T022 [P] [US1] Integration tests in `backend/tests/integration/test_us1_direct_answer.py`: (a) ingest the sample corpus, ask "How do I pay a parking ticket?", and assert `type == "answered"` with a source URL present; (b) ingest a manifest pair where a child page/attachment is a separate entry from its parent (per T025), ask a question whose answer requires content from both, and assert the `answered` result's `sources` includes both the parent and child entries and `directAnswer`/`explanation` reflect the combined content — not just the parent's (FR-011, FR-015, US1 AC2)

### Implementation for User Story 1

- [ ] T023 [P] [US1] Implement the HTML parser in `backend/app/ingestion/parsers/html_parser.py` using `beautifulsoup4`: extract structure-preserving text matching `SourceChunk.structureContext` in `data-model.md`, explicitly preserving — per FR-014/FR-015 — heading hierarchy (heading path), numbered procedures (step order), bullet lists (list membership), table structure (row/column/header association), and content inside expandable/accordion elements (typically present in the raw HTML even when visually collapsed by CSS/JS, so `beautifulsoup4` can read it directly)
- [ ] T024 [P] [US1] Implement the PDF parser in `backend/app/ingestion/parsers/pdf_parser.py` using `pypdf`: extract text with page/section structure preserved
- [ ] T025 [US1] Implement the approved-source manifest format and loader in `backend/app/ingestion/sources.json` (data) and `backend/app/ingestion/run.py` (loader logic): each entry is `{url, title, campus?, academicTerm?, courseName?, programName?, studentLevel?}` — `url` and `title` are required on every entry (`title` is written by the manifest curator, never scraped from the page — `data-model.md`'s `SourceChunk.title` note); the rest are optional. An explicit, hand-curated list, not crawler-discovered; whether to invoke the HTML or PDF parser (T023/T024) is determined from the `url`'s extension/content-type at fetch time, not a stored field. A top-level page's important linked child page or attached document (FR-011, FR-015) MUST be its own explicit manifest entry, with its own `title`
- [ ] T026 [US1] Implement the structure-aware chunker in `backend/app/ingestion/chunker.py`: split parsed content into chunks, each carrying the manifest entry's `url` and `title` (required — every chunk cites back to its source), `structureContext`, plus whatever optional `campus`/`academicTerm`/`courseName`/`programName`/`studentLevel` values the manifest entry supplied for that source — fields the manifest doesn't supply are omitted from the chunk's metadata, never defaulted or guessed
- [ ] T027 [US1] Implement the ingestion CLI entrypoint in `backend/app/ingestion/run.py` (invoked as `uv run python -m app.ingestion.run --manifest app/ingestion/sources.json`): for each manifest entry, fetch/read the source, parse it (T023/T024), chunk it (T026), call `retrieval.delete_chunks_for_url(url)` (T015) to remove any chunks already stored for that `url`, then embed each new chunk via `retrieval.embed_text()` (T014) and write it via `retrieval.add_chunks()` (T015) — each chunk gets its own Chroma ID derived from `url` + chunk index, so re-ingestion replaces rather than duplicates without multiple chunks colliding on one ID (per `data-model.md` `SourceChunk` validation)
- [ ] T028 [US1] Implement retrieval query logic in `backend/app/retrieval.py`: embed the question via `embed_text()`, call `query()` over-fetching more than `k` similar chunks (e.g. `k * 4`), accepting an optional resolved-context argument (whichever of campus/program/studentLevel/academicTerm `clarification.extract_explicit_context` resolved, once T040/T053/T060 exist) so the post-similarity-search eligibility filters added in T041/T055/T060 (research.md §12) can be applied to those candidates and the result trimmed back down to `k`; over-fetching compensates for the filter step dropping some candidates without needing Chroma's `where` clause to express "field absent" filtering itself. Separately, also accept the raw question text so T051's independent `courseName` boost (not resolved-context-driven) can be applied
- [ ] T029 [US1] Implement the grounded-generation prompt and call in `backend/app/generation.py`: construct a prompt instructing Gemini to answer ONLY from the retrieved chunks and to note uncertainty in prose only when retrieved content shows explicit signs of an older source's staleness (never for a material conflict between sources — `grounding.py`, T034, catches that before generation is ever called, and returns `cannot_answer` instead), producing `{directAnswer, explanation, sources}` (FR-003, FR-004, FR-019). When the question spans multiple sub-topics and only some are answerable from retrieved chunks (spec.md Edge Cases), instruct Gemini to answer the resolvable part in `directAnswer`/`explanation` and state in prose, within `explanation`, that the other part can't be reliably answered and should be directed to the appropriate office — there is no separate structured field for this (`answered` has no `officeName`); this is expressed as prose only
- [ ] T030 [US1] Implement the `POST /api/query` handler skeleton in `backend/app/api/query.py` following T020's authoritative orchestration order (at this point in the build, only steps 1, 4, 8, 9, 10 exist — validation, retrieval via `retrieval.py` with no resolved-context filters yet, generation via `generation.py`, the `sources`-non-empty check, and the response — since the private-data check, context extraction/clarification, and grounding steps are added by later tasks), producing the `"answered"` result shape from `contracts/query-api.md`
- [ ] T031 [US1] Implement citation rendering in `frontend/src/components/AnswerMessage.jsx`: display `directAnswer`, `explanation`, and a list of source titles/links from `sources`

**Checkpoint**: User Story 1 is fully functional and independently testable — this is the MVP.

---

## Phase 4: User Story 2 - Fail Safely When an Answer Cannot Be Reliably Given (Priority: P1)

**Goal**: When approved information is missing, insufficient, ambiguous, contradictory, outdated, or the question requires private/personalized data, the chatbot clearly says it cannot reliably answer and refers the student to the appropriate office — instead of guessing.

**Independent Test**: Submit questions known to fall outside the sample corpus, and a private-data-style question (e.g., "Why did my registration fail?"). Confirm the chatbot declines with `type == "cannot_answer"`, includes an office referral, and never fabricates an answer.

### Tests for User Story 2

- [ ] T032 [P] [US2] Contract tests in `backend/tests/contract/test_query_cannot_answer.py`: (a) `POST /api/query` returns `type == "cannot_answer"` with a non-empty `officeName` when no relevant chunks are retrieved (`reason == "insufficient_source_info"`); (b) against two ingested sources that materially conflict on the fact needed to answer, `POST /api/query` returns `type == "cannot_answer"` with `reason == "conflicting_sources"` and a non-empty `officeName` — never `type == "answered"` (FR-017)
- [ ] T033 [P] [US2] Integration test: ask "Why did my registration fail?" and assert `reason == "private_data_required"`, in `backend/tests/integration/test_us2_fail_safe.py`

### Implementation for User Story 2

- [ ] T034 [US2] Implement `backend/app/grounding.py` as a single module combining: (a) a private-data-question heuristic (FR-020, FR-008 edge case): flag phrasing that combines a first-person possessive ("my"/"I") with an account-specific noun (registration, grades, financial aid, account, application, enrollment) and a status/outcome word (failed, denied, wrong, error, why); e.g., "why did my registration fail" — this is deliberately a narrow, high-precision heuristic, since a false negative here just falls through to the sufficiency check (b), while a false positive would wrongly refuse an answerable general question, (b) insufficient-grounding detection (score retrieved chunks' relevance, flag `insufficient_source_info` below a threshold — FR-007), (c) conflicting-source detection: two retrieved chunks are a *material* conflict when they give different values for the same field needed to answer the question (e.g., different dates/dollar amounts/campuses/required steps for the same term+action) — a difference in unrelated details across chunks is NOT material and does not trigger this check. When a material conflict is detected, this ALWAYS flags `reason = "conflicting_sources"` and short-circuits before generation is ever called — grounding never lets an `answered` response pick one side (FR-017), (d) out-of-scope detection (edge case): flag `out_of_scope_topic`, checked independently of retrieval quality, when the question carries no signal connecting it to PNW/university matters at all — no match against FR-021's minimum topic list, no campus/course/program mention, and no PNW-specific term. This is conceptually distinct from (b): (d) is "this isn't a university question" (e.g., "what's the capital of France"), while (b) is "this is a plausibly-in-scope university question, but the retrieved chunks don't sufficiently support an answer" — a question that passes (d) but still finds nothing relevant falls through to (b) instead, and (e) explicit-outdated-evidence detection: a question is *time-sensitive* when its retrieved chunks carry an `academicTerm` value or the question matches a deadline/date topic (e.g., "deadline", "due", "when is", "last day to"); for such a question, when the only relevant retrieved chunks contain an explicit old date/term (per FR-018) with no current/newer evidence also supporting the answer, flag `insufficient_source_info`; when newer evidence is also retrieved, do NOT flag here — leave the uncertainty to be stated in `explanation` by `generation.py` (T029/T062). This does not read or require any persisted freshness field — it inspects retrieved `content`/`structureContext` directly at query time (`data-model.md`'s "No freshness field" note). Each check returns a `reason` for a `cannot_answer` response when triggered
- [ ] T035 [US2] Wire `grounding.py`'s checks into `backend/app/api/query.py` at their respective steps (2 and 7a–7d) in T020's authoritative orchestration order — do not redefine that order here: return `cannot_answer` with `officeName` (from T036) when any check triggers, otherwise proceed toward generation
- [ ] T036 [US2] Implement referral-office lookup as a small function within `backend/app/grounding.py`: map topic/reason to an appropriate PNW office name, seeded from the topic list in FR-021/FR-023
- [ ] T037 [P] [US2] Implement referral/cannot-answer rendering in `frontend/src/components/ReferralMessage.jsx`: display the limitation `message` and the `officeName`

**Checkpoint**: User Stories 1 AND 2 both work independently — the core trust and safety behaviors are complete (MVP).

---

## Phase 5: User Story 3 - Resolve Campus-Dependent Questions Correctly (Priority: P2)

**Goal**: When a question's correct answer depends on campus (Hammond or Westville), the chatbot either determines the campus from context or asks the student to clarify, rather than assuming.

**Independent Test**: Ask a campus-dependent question with and without a campus named. Confirm a campus-named question is answered using only that campus's sources, and a campus-unspecified question triggers a `clarification_needed` prompt with Hammond/Westville options.

### Tests for User Story 3

- [ ] T038 [P] [US3] Contract test: `POST /api/query` returns `type == "clarification_needed"` with `missingContext == "campus"` and `options == ["Hammond", "Westville"]` for a campus-ambiguous question, in `backend/tests/contract/test_query_clarification_campus.py`
- [ ] T039 [P] [US3] Integration test: ask a campus-ambiguous parking question, answer the clarification with `context.campus == "hammond"`, and assert the follow-up `"answered"` result only cites Hammond-tagged sources, in `backend/tests/integration/test_us3_campus_disambiguation.py`

### Implementation for User Story 3

- [ ] T040 [US3] Implement `backend/app/clarification.py` with its two functions, starting with the campus dimension: `extract_explicit_context(question_text, request_context)` resolves `campus` from `request_context.campus` if present, else from an explicit "Hammond"/"Westville" mention in `question_text`; `find_missing_context(retrieved_chunks, resolved_context)` flags campus as missing when `resolved_context.campus` is still unset AND the retrieved chunks for the topic vary by campus (FR-010). This module will grow to own all four dimensions (program, student_level, academic_term — added in T053/T060) within these same two functions, never a function per dimension
- [ ] T041 [US3] Implement campus metadata filtering in `backend/app/retrieval.py` using the shared context-dimension eligibility rule (research.md §12 — NOT a bare `where={"campus": {"$in": [campus, "both"]}}` Chroma filter, which would wrongly exclude chunks that omit `campus` entirely): when `extract_explicit_context` (T040) resolves a `campus`, apply a post-similarity-search filter in Python that keeps a candidate chunk when its `campus` metadata is absent (context-independent, always eligible), `"both"`, or equals the resolved `campus` exactly, and drops it only when `campus` is present and set to the *other* specific campus. Implement this as one small shared helper (e.g. `_matches_context_dimension(chunk_metadata, field, resolved_value, both_value="both")`) that T055 and T060 reuse for their own dimensions rather than each reimplementing the same eligibility logic
- [ ] T042 [US3] Wire campus clarification (T040) into `backend/app/api/query.py` at steps 3 and 5a of T020's authoritative orchestration order (`extract_explicit_context` contributes campus resolution at step 3; `find_missing_context`'s campus check is evaluated first among the four dimensions at step 5) — do not redefine that order here: when campus is required but neither the question text nor `context.campus` resolves it, return `"clarification_needed"` (`missingContext="campus"`, `options=["Hammond","Westville"]`)
- [ ] T043 [P] [US3] Implement clarification-prompt rendering in `frontend/src/components/ClarificationPrompt.jsx`: render `promptText` plus clickable option buttons (when `options` is present, e.g. campus) that resend the query with `context` populated; when `options` is absent (e.g. `academic_term`), render a free-text input instead that resends the query with `context.academicTerm` set (US4's T056 extends this same component for the `program` case)

**Checkpoint**: User Stories 1, 2, and 3 are all independently functional.

---

## Phase 6: User Story 4 - Understand Course Prerequisites and Program Requirements (Priority: P2)

**Goal**: Prerequisite and program-requirement answers correctly attribute each prerequisite to its specific course (never a different one) and combine catalog + procedural information into one answer, inventing nothing beyond approved sources.

**Independent Test**: Ask about a specific course's prerequisites and confirm the returned prerequisites match exactly that course's catalog entry; ask a grad plan-of-study question and confirm only sourced steps are returned.

### Tests for User Story 4

- [ ] T044 [P] [US4] Contract test: `POST /api/query` for a course-prerequisite question returns sources whose underlying chunk `courseName` metadata matches the asked course, in `backend/tests/contract/test_query_prerequisites.py`
- [ ] T045 [P] [US4] Integration test: ask "What are the prerequisites for CS 240?" against a sample catalog entry with known prerequisites and assert the answer lists exactly those prerequisites, in `backend/tests/integration/test_us4_prerequisites.py`
- [ ] T046 [P] [US4] Contract test: `POST /api/query` for a program-requirements question that doesn't name a program, where the sample corpus covers multiple programs (`programName` metadata), returns `type == "clarification_needed"` with `missingContext == "program"` and `options` omitted, in `backend/tests/contract/test_query_clarification_program.py`
- [ ] T047 [P] [US4] Contract test: `POST /api/query` for a plan-of-study question that doesn't specify academic level, where the sample corpus has level-specific pages (`studentLevel` metadata), returns `type == "clarification_needed"` with `missingContext == "student_level"` and `options == ["Undergraduate", "Graduate"]`, in `backend/tests/contract/test_query_clarification_student_level.py`
- [ ] T048 [US4] Integration test: ask a plan-of-study question without student level, answer the clarification with `context.studentLevel == "graduate"`, and assert the follow-up `"answered"` result only cites graduate-tagged sources, in `backend/tests/integration/test_us4_student_level_disambiguation.py`

### Implementation for User Story 4

- [ ] T049 [US4] Extend `backend/app/ingestion/parsers/html_parser.py` to preserve each catalog entry's prerequisite wording intact within the chunk's `content`/`structureContext` (per FR-016 — "MUST NOT attribute a prerequisite to the wrong course"). The parser does NOT extract or infer `courseName` — that comes only from the approved-source manifest entry for that catalog page (T025/T026); if a catalog entry's manifest row doesn't supply `courseName`, the resulting chunk simply omits it rather than guessing it from the page content
- [ ] T050 [US4] Extend `backend/app/ingestion/chunker.py` to carry, for program/plan-of-study manifest entries, the `programName` identifier (e.g., "B.S. Computer Science" — the stable key used for retrieval filtering and clarification; requirement details stay in `content`/`structureContext`) and `studentLevel` (`"undergraduate"`/`"graduate"`/`"both"`) when the manifest entry supplies them
- [ ] T051 [US4] Implement course-name-aware retrieval boosting in `backend/app/retrieval.py`: when the question text names a specific course (e.g., "CS 240"), prefer chunks whose `courseName` metadata matches. `courseName` is not one of `clarification.py`'s four dimensions (FR-009 covers only campus/program/student_level/academic_term), so this is a standalone raw-text-mention boost, independent of `extract_explicit_context`/`resolved_context` — unlike T055's `programName`/`studentLevel` filtering below, which IS driven by the resolved context. `programName` boosting/filtering belongs solely to T055; this task does not touch `programName`, to avoid two code paths acting on the same field
- [ ] T052 [US4] Extend the `backend/app/generation.py` prompt to explicitly instruct Gemini to keep each prerequisite attributed to the course named in its source chunk's `courseName` metadata, never merging prerequisites across courses
- [ ] T053 [US4] Extend `backend/app/clarification.py`'s two functions with the program and student_level dimensions (second and third, after campus): `extract_explicit_context` additionally resolves `program` from `request_context.program` or an explicit program name in the question text, and `studentLevel` from `request_context.studentLevel` or "undergraduate"/"graduate" wording; `find_missing_context` additionally flags `missingContext = "program"` when a program-requirements question's program is still unresolved and the retrieved chunks span more than one `programName`, and flags `missingContext = "student_level"` when relevant retrieved content varies by `studentLevel` and it's still unresolved (FR-009)
- [ ] T054 [US4] Wire program/student-level clarification (T053) into `backend/app/api/query.py` at steps 3 and 5b–5c of T020's authoritative orchestration order (`extract_explicit_context` contributes program/student_level resolution at step 3; `find_missing_context`'s program then student_level checks are evaluated after campus, before academic_term, at step 5) — do not redefine that order here: return `"clarification_needed"` (`missingContext="program"`, `options` omitted) or (`missingContext="student_level"`, `options=["Undergraduate","Graduate"]`) when `clarification.py` (T053) flags ambiguity
- [ ] T055 [US4] Implement program/student-level metadata filtering in `backend/app/retrieval.py` using T041's shared eligibility helper (research.md §12): when `extract_explicit_context` (T040/T053) resolves a `program`, keep a chunk when its `programName` is absent (context-independent), or equals the resolved program exactly (`programName` has no `"both"` sentinel — only the absent/exact-match cases apply); when it resolves a `studentLevel`, keep a chunk when its `studentLevel` is absent, `"both"`, or equals the resolved level exactly. This is the sole `programName`-retrieval-logic owner (T051 is `courseName`-only — see T051's note)
- [ ] T056 [US4] Extend `frontend/src/components/ClarificationPrompt.jsx` (built in T043) to support a free-text input fallback for `missingContext == "program"` (where `options` is absent), resending the query with `context.program` set

**Checkpoint**: User Stories 1–4 are all independently functional.

---

## Phase 7: User Story 5 - Get Accurate, Term-Correct Deadline Information (Priority: P3)

**Goal**: Deadline answers correctly match date, term, action, and condition, with no cross-term mixing; a term-ambiguous deadline question triggers clarification or an explicit statement of which term the answer covers.

**Independent Test**: Ask for a specific term's specific deadline and confirm the exact date/term/condition; ask a deadline question without a term when more than one applies and confirm either a clarification prompt or an explicit term statement.

### Tests for User Story 5

- [ ] T057 [P] [US5] Contract test in `backend/tests/contract/test_query_deadlines.py`: `POST /api/query` for a term-specified deadline question (`context.academicTerm` set, or the term named in the question text) returns an `explanation` whose stated term matches the asked term exactly, and `sources` draws only from chunks tagged with that `academicTerm` — asserting that resolving an explicit term actually restricts retrieval rather than only affecting the generated text
- [ ] T058 [P] [US5] Integration test: ingest a sample deadline table with two terms, ask without specifying a term, and assert either `clarification_needed` (`missingContext == "academic_term"`) or an `answered` result whose `explanation` states the term used, in `backend/tests/integration/test_us5_deadline_terms.py`

### Implementation for User Story 5

- [ ] T059 [US5] Extend `backend/app/ingestion/chunker.py` (not `html_parser.py` — T023 already preserves table row/column/header association at the parsing level; this task is about chunk *boundaries*, a distinct concern) so deadline-table content is split at row-level granularity (or another boundary that keeps one term/action/condition tuple together): no single `SourceChunk` may span rows belonging to two different terms, and no chunk boundary may separate a date from the term/condition `structureContext` already gives it. This is what makes FR-013's "must not be mixed across unrelated rows, columns, or terms" hold at retrieval time, not just at parse time (per `data-model.md` `SourceChunk.structureContext`)
- [ ] T060 [US5] Extend `backend/app/clarification.py`'s two functions with the academic_term dimension (fourth and last, after campus/program/student_level): `extract_explicit_context` additionally resolves `academicTerm` from `request_context.academicTerm` or an explicit term mention in the question text; `find_missing_context` additionally flags `missingContext = "academic_term"` — checked last, after campus/program/student_level — when a deadline question's term is still unresolved and multiple applicable terms exist among the retrieved chunks (FR-009). Also implement `academicTerm` metadata filtering in `backend/app/retrieval.py` using T041's shared eligibility helper (research.md §12), mirroring T055's program filter: when `extract_explicit_context` resolves an `academicTerm`, keep a chunk when its `academicTerm` is absent (term-independent content, e.g. a general policy page) or equals the resolved term exactly (`academicTerm` has no `"both"` sentinel); drop a chunk whose `academicTerm` is present and set to a *different* term — this is what prevents cross-term mixing (FR-013) while still surfacing term-independent sources. Leave the dimension unfiltered entirely (never invent a term) when it isn't resolved
- [ ] T061 [US5] Wire term clarification (T060) into `backend/app/api/query.py` at steps 3 and 5d of T020's authoritative orchestration order (`extract_explicit_context` contributes academic-term resolution at step 3; `find_missing_context`'s academic-term check is evaluated last among the four dimensions at step 5) — do not redefine that order here: return `"clarification_needed"` (`missingContext="academic_term"`) when `clarification.py` flags ambiguity, else proceed with the resolved/explicit term
- [ ] T062 [US5] Extend `backend/app/generation.py` to state the exact date/term/condition from the matched chunk(s) in `explanation`, preserving them exactly as ingested (no recombination across rows)

**Checkpoint**: All user stories (US1–US5) are independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T063 [P] Add structured request/response logging in `backend/app/main.py` (per `constitution.md`'s Development Workflow principle) — log `type`, retrieval hit count, and latency; do not log full question text beyond what's needed for debugging, since no student identity is ever captured (FR-020)
- [ ] T064 [P] Write unit tests for grounding/clarification/chunking logic in `backend/tests/unit/` covering: sufficiency scoring; material-conflict detection resolving to `reason == "conflicting_sources"` (never an answered result) — FR-017; explicit-outdated-evidence detection on a time-sensitive question with only an old source resolving to `reason == "insufficient_source_info"`, and the contrasting case where newer evidence is also present; `extract_explicit_context`/`find_missing_context` for campus/program/student_level/academic_term; academicTerm (and campus/program/studentLevel) retrieval filtering actually restricting which chunks come back; and chunker structure preservation — required by `constitution.md`'s Development Workflow principle
- [ ] T065 [P] Add frontend component tests with React Testing Library + Vitest for `AnswerMessage`, `ReferralMessage`, and `ClarificationPrompt`, in `frontend/src/components/*.test.jsx`
- [ ] T066 Run and document the full `quickstart.md` validation checklist manually: all 15 numbered scenarios plus the Manual evaluation question set table, recording pass/fail for each
- [ ] T067 [P] Write the root `README.md` (project name, one-sentence purpose, note that this is a PNW course-project design, pointer to `specs/001-pnw-student-chatbot/`, stack summary, Docker Compose quickstart note) and reference `quickstart.md`'s `docker compose up --build` run steps

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories. Includes T020, the single authoritative `query.py` orchestration order that all later story tasks touching that file (T030, T035, T042, T054, T061) must implement into rather than redefine.
- **User Stories (Phase 3–7)**: All depend on Foundational phase completion
  - US1 and US2 are both P1 and should be done first (together they form the MVP's trust core)
  - US3 and US4 (P2) can proceed once Foundational is done; US3 benefits from US1's retrieval/generation path existing, US4 likewise, but neither requires US2/US3/US4 to be complete first
  - US5 (P3) builds on the table-parsing groundwork started in US1's ingestion tasks but is independently testable once its own tasks are done
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) — no dependency on other stories. This is the MVP.
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) — reuses US1's retrieval call, and adds its own `grounding.py`; independently testable via its own contract/integration tests.
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) — adds campus filtering on top of US1's retrieval/generation path, and starts `clarification.py`; independently testable.
- **User Story 4 (P2)**: Can start after Foundational (Phase 2) — extends US1's ingestion parsers, and extends `clarification.py` (T053–T054, T056); independently testable.
- **User Story 5 (P3)**: Can start after Foundational (Phase 2) — extends US1's ingestion parsers for tables and extends `clarification.py` (T060–T061); independently testable.

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Ingestion/parsing before retrieval; retrieval before generation; generation before the API handler; API handler before frontend rendering
- Story complete before moving to the next priority (recommended order: US1 → US2 → US3 → US4 → US5)

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] (T017–T019) can run in parallel once T012–T016 land
- Once Foundational completes, US1 and US2 can be staffed in parallel by different people (US2 depends only on US1's retrieval call existing, not on US1 being fully polished)
- All tests for a given user story marked [P] can run in parallel
- Within US1, the two parser tasks (T023, T024) can run in parallel
- Within Phase 8, T063–T065 and T067 can run in parallel with each other

---

## Parallel Example: User Story 1

```bash
# Launch both User Story 1 tests together:
Task: "Contract test for answered result in backend/tests/contract/test_query_answered.py"
Task: "Integration test for direct answer in backend/tests/integration/test_us1_direct_answer.py"

# Launch both ingestion parsers together:
Task: "HTML parser in backend/app/ingestion/parsers/html_parser.py"
Task: "PDF parser in backend/app/ingestion/parsers/pdf_parser.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 — both P1)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (direct grounded answers)
4. Complete Phase 4: User Story 2 (fail-safe/referral) — both P1 stories are needed together, since the spec treats accurate answers and safe failure as equally important trust requirements
5. **STOP and VALIDATE**: Run the applicable `quickstart.md` scenarios (1–5) for US1/US2 independently
6. Demo if ready — this is the MVP

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 + US2 → test independently → demo (MVP)
3. Add US3 (campus disambiguation) → test independently → demo
4. Add US4 (prerequisites/program requirements) → test independently → demo
5. Add US5 (term-correct deadlines) → test independently → demo
6. Phase 8 polish once all desired stories are in

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (then User Story 2, since it builds on US1's retrieval call)
   - Developer B: User Story 3
   - Developer C: User Story 4, then User Story 5
3. Stories complete and integrate independently through the shared `POST /api/query` contract

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently
- Docker Compose is the standard/required run environment (T008–T011); no Next.js, no paid LLM/embedding API, no crawler, no performance benchmark, no custom evaluation runner — per `constitution.md` Principle V and `plan.md`'s Technical Context
