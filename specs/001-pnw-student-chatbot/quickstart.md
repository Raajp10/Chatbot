# Quickstart: PNW Student Knowledge Chatbot

**Feature**: 001-pnw-student-chatbot | **Date**: 2026-09-19 (re-simplified)

This guide validates the feature end-to-end once implemented, using the course-required local stack: FastAPI + React, no Docker, Google Gemini free-tier APIs, and a local ChromaDB store. It references `data-model.md` and `contracts/query-api.md` rather than duplicating them.

## Prerequisites

- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/) installed
- Node.js 20 LTS and `npm`
- A Google Gemini API key (free tier — see course material for how to obtain one)
- No database server and no Docker are required — ChromaDB persists to a local folder automatically
- A small, hand-curated approved-source manifest (`backend/app/ingestion/sources.json`) listing a handful of approved PNW pages/PDFs, each entry supplying `url` and `title` at minimum, covering: an add/drop deadline table, a course-with-prerequisites catalog entry, a parking-ticket policy page, one page that applies to only a single campus, a program-requirements page for at least two distinct programs, a plan-of-study page that differs for undergraduate vs. graduate students, and one page carrying an explicit prior-year date alongside a newer page covering the same topic. Any important child page or attached PDF must be its own explicit entry in the manifest (there is no crawler to discover it automatically — see `research.md` §6). Automated tests may use separate local fixtures that stand in for sources; the approved manifest itself always points at official/approved PNW content, never fabricated or placeholder pages.

## Setup

### Backend

```bash
cd backend
uv sync                      # installs FastAPI, chromadb, google-genai, etc. from pyproject.toml
cp .env.example .env         # set GEMINI_API_KEY
```

### Frontend

```bash
cd frontend
npm install
```

No migration step is needed — ChromaDB creates its local persistent store (`backend/data/chroma/`) automatically the first time it's used.

## Ingest the approved-source corpus

```bash
cd backend
uv run python -m app.ingestion.run --manifest app/ingestion/sources.json
```

Expected outcome: for each manifest entry, its content is fetched/read, parsed, chunked, embedded, and written to the local Chroma store as one or more `SourceChunk` records, carrying `structureContext` and any `campus`/`academicTerm`/`courseName`/`programName`/`studentLevel` values the manifest supplied — fields the manifest didn't supply are simply omitted, never guessed. Re-running the same command is idempotent (re-ingesting a URL replaces its prior chunks rather than duplicating them).

## Run the app

```bash
# terminal 1
cd backend && uv run uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend && npm run dev
```

Open the standalone chat page (per FR-026, no embedding) at the address `npm run dev` prints (typically `http://localhost:5173`). Confirm the audience disclaimer (FR-024) is visible — it's static text rendered by `DisclaimerBanner.jsx`, not returned by the API.

## Validation scenarios (map to spec Acceptance Scenarios)

Each scenario below should be run both through the UI and as a direct `POST /api/query` call (see `contracts/query-api.md` for the exact response shape to assert against).

1. **Direct grounded answer (US1)** — Ask a question with a clear answer in the sample corpus (e.g., "How do I pay a parking ticket?"). Expect `type = "answered"` with a non-empty `sources` list and a plain-language `explanation`.

2. **Combined top-level + child page (US1, AC2)** — Ask a question whose answer requires a linked child page or attached PDF (make sure that child page/PDF has its own manifest entry). Expect the answer to reflect the combined content, and `sources` to include the child/attached document.

3. **Fail-safe on missing info (US2)** — Ask a question outside the sample corpus's topics. Expect `type = "cannot_answer"` with `reason = "insufficient_source_info"` and a non-empty `officeName`. Confirm no fabricated answer appears.

4. **Fail-safe on private data (US2, AC2)** — Ask something like "Why did my registration fail?" Expect `type = "cannot_answer"` with `reason = "private_data_required"`.

5. **Conflicting sources (US2, AC3)** — Ingest two manifest entries that materially disagree on one fact, then ask about it. Expect `type = "cannot_answer"` with `reason = "conflicting_sources"` and a non-empty `officeName` — never an `answered` result, and never a silent (or explained) pick of one source over the other.

6. **Campus disambiguation, unspecified (US3, AC2)** — Ask a campus-dependent question without naming a campus (e.g., a parking question). Expect `type = "clarification_needed"` with `missingContext = "campus"` and `options = ["Hammond", "Westville"]`. Answer it by sending a follow-up request with `context.campus` set, then confirm the response returns the correct campus-specific `answered` result.

7. **Campus disambiguation, specified (US3, AC1)** — Ask the same question but name a campus explicitly. Expect a direct `answered` result using only that campus's sources.

8. **Prerequisite attribution (US4, AC1)** — Ask for a specific course's prerequisites. Expect the returned prerequisites to match exactly that course's catalog entry (the `courseName` metadata on that chunk, with the prerequisite wording itself coming from the chunk's `content` — see `data-model.md`), not a different course's.

9. **Plan of study (US4, AC2)** — Ask a graduate plan-of-study question. Expect steps present in the sample corpus only — nothing invented.

10. **Term-correct deadline (US5, AC1)** — Ask for a specific term's specific deadline. Expect the exact date/term/condition triple from the sample corpus, stated in `explanation`, with no cross-term mixing.

11. **Deadline term ambiguous (US5, AC2)** — Ask a deadline question without a term, where the sample corpus has more than one applicable term. Expect either a `clarification_needed` (`missingContext = "academic_term"`) or an `answered` result whose `explanation` explicitly states which term it refers to.

12. **Missing-program clarification (FR-009)** — Ask a program-requirements question without naming a program, where the sample corpus covers at least two distinct programs (via `programName` metadata). Expect `type = "clarification_needed"` with `missingContext = "program"` and `options` omitted. Answer with `context.program` set to one program's name, then confirm the follow-up `answered` result only cites that program's sources.

13. **Missing-student-level clarification (FR-009)** — Ask a plan-of-study question without specifying undergraduate/graduate, where the sample corpus has level-specific pages (`studentLevel` metadata). Expect `type = "clarification_needed"` with `missingContext = "student_level"` and `options = ["Undergraduate", "Graduate"]`. Answer with `context.studentLevel = "graduate"`, then confirm the follow-up `answered` result only cites graduate-tagged sources.

14. **Explicitly outdated content (FR-018)** — Ingest the manifest entry with an explicit old date alongside its newer counterpart, then ask about the topic they both cover. Expect either an `answered` result whose `explanation` notes the information may be out of date (when the newer source is also retrieved and used), or `type = "cannot_answer"` (`reason = "insufficient_source_info"`) if only the old page is relevant and the topic is time-sensitive.

15. **Multi-sub-topic question (Edge Case)** — Ask a question combining an answerable sub-topic and one that isn't (e.g., a covered deadline question plus "...and why did my application get rejected?"). Expect `type = "answered"` whose `directAnswer`/`explanation` address the resolvable part and whose `explanation` also states, in prose, that the other part can't be reliably answered and names an office to contact — or `type = "cannot_answer"` if neither part clears the sufficiency bar. Confirm nothing is fabricated for the unanswerable part, and that no field other than `explanation` carries the referral (`answered` has no `officeName`).

## Manual evaluation question set (SC-001–SC-005)

No scripted evaluation runner exists for v1 (`research.md` §11) — run these questions by hand against the running system after ingestion and record pass/fail directly in this table. "Pass" means: grounded/traceable to a source for `answered` results (SC-001/SC-002), a non-empty `officeName` for `cannot_answer` results (SC-003/SC-007), the correct campus for campus-dependent questions (SC-004), and the correct term/date/condition for deadline questions (SC-005), with no fabricated information in any case.

| # | Question | Category | Expected `type` | Pass/Fail |
|---|---|---|---|---|
| 1 | "How do I pay a parking ticket?" | Parking / policy | `answered` | |
| 2 | "What's the add/drop deadline for [term]?" | Academic deadline | `answered` | |
| 3 | "What's the add/drop deadline?" (term unspecified, corpus has 2+ terms) | Academic deadline | `clarification_needed` (academic_term) or `answered` with term stated | |
| 4 | "How do I register for classes?" | Registration | `answered` | |
| 5 | "What happens if I'm placed on academic probation?" | Academic standing | `answered` | |
| 6 | "How do I appeal a grade?" | Grade appeals | `answered` | |
| 7 | "What's the financial aid deadline for [term]?" | Financial aid | `answered` | |
| 8 | "Where do I park?" (campus unspecified, answer differs by campus) | Parking / campus | `clarification_needed` (campus) | |
| 9 | "Where do I park at the Westville campus?" | Parking / campus | `answered`, Westville sources only | |
| 10 | "What are the prerequisites for [a specific course]?" | Prerequisites | `answered`, correct course | |
| 11 | "What are the requirements for [a specific program]?" (program named) | Program requirements | `answered` | |
| 12 | "What are the program requirements?" (program unspecified, corpus has 2+ programs) | Program requirements | `clarification_needed` (program) | |
| 13 | "How do I submit my plan of study?" (level unspecified, corpus has level-specific pages) | Plan of study | `clarification_needed` (student_level) | |
| 14 | "Why did my registration fail?" | Private data | `cannot_answer` (private_data_required) | |
| 15 | A question outside the corpus's topics entirely | Out of scope | `cannot_answer` (insufficient_source_info or out_of_scope_topic) | |

## Success criteria checks

- SC-001/SC-002: For every `answered` result across the scenarios and evaluation table above, confirm each cited source actually supports the stated answer (manual spot-check against the sample corpus).
- SC-003/SC-007: For every `cannot_answer` result, confirm a non-empty `officeName` is present.
- SC-004: For campus-dependent scenarios, confirm no answer ever uses the wrong campus's data.
- SC-005: For deadline scenarios, confirm date/term/condition are never cross-mixed.
- SC-006: Usability testing (≥80% of testers report the chatbot was easier than manual searching) is out of scope for this local validation pass and is tracked separately, per `spec.md`.

## Cleanup

```bash
rm -rf backend/data/chroma   # deletes the local vector store; re-run ingestion to rebuild it
```
