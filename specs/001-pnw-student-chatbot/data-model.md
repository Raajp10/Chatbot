# Phase 1 Data Model: PNW Student Knowledge Chatbot

**Feature**: 001-pnw-student-chatbot | **Date**: 2026-09-19 (re-simplified)

This revision reduces the persisted model to a single conceptual entity, `SourceChunk`, and the transient request/response shapes to exactly the fields the API contract actually needs. Per the constitution's Simplicity principle: if a field's value cannot reliably be provided from an approved source, it is omitted rather than stored as a placeholder or guessed.

## Persisted entity (ChromaDB)

### SourceChunk

The only persisted entity. One retrievable chunk of approved PNW content (not a whole document), so structure (FR-013/FR-014) is preserved at the granularity actually cited. Stored as a Chroma document: `content` is the embedded text, everything else below is Chroma metadata.

| Field | Type | Notes |
|---|---|---|
| `url` | string | Canonical link to the official source, used for citation (FR-006) |
| `title` | string | Page/document title. Required, and supplied directly by the approved-source manifest entry for that source (`research.md` §6) — not scraped from HTML `<title>`/PDF metadata, since that's not guaranteed to exist or be meaningful for every approved source |
| `content` | text | The chunk's text, with structure preserved (heading path, table row context) — this is what gets embedded |
| `structureContext` | string, optional | E.g. "Financial Aid > Deadlines > Fall 2026 table, row: Add/Drop" — preserves a relationship a flat chunk would otherwise lose (FR-013, FR-014) |
| `campus` | `"hammond" \| "westville" \| "both"`, optional | Omitted when campus applicability isn't established by the source — never guessed |
| `academicTerm` | string, optional | E.g. "Fall 2026"; omitted when the content is term-independent or the source doesn't state a term |
| `courseName` | string, optional | Set only for course-catalog chunks, supplied explicitly in the approved-source manifest for that entry (`research.md` §6) — not inferred or extracted by the parser. Prerequisite wording stays in `content`/`structureContext`; `courseName` is enough to keep it correctly attributed, so no separate prerequisites field is needed. Omitted, never guessed, when the manifest doesn't supply it |
| `programName` | string, optional | Set only for program-catalog chunks; the stable identifier for the program this chunk describes (e.g., "B.S. Computer Science") — used for retrieval filtering and for detecting when a program-requirements question needs clarification (FR-009). Program requirement details themselves stay in `content`/`structureContext`; `programName` is identifying/filtering metadata only |
| `studentLevel` | `"undergraduate" \| "graduate" \| "both"`, optional | Set when a chunk's content applies to only one academic level (e.g., a graduate-only plan-of-study page); omitted when level-independent or not stated — used for FR-009 clarification when an answer differs by level |

**Retrieval eligibility for the optional context fields** (`campus`, `programName`, `studentLevel`, `academicTerm`): each is populated only when the source establishes it — omitted, never guessed, otherwise. This means "omitted" itself carries meaning at retrieval time: once a dimension's value is resolved from the question (`clarification.extract_explicit_context`), a chunk is eligible for that resolved value when it omits the field entirely (a context-independent, generally-applicable source), when its field is the sentinel `"both"` (defined only for `campus`/`studentLevel`), or when its field equals the resolved value exactly. A chunk whose field is present and set to a *different* specific value is excluded. See `research.md` §12 for the full rule and why a naive "field is one of [resolved value, both]" filter would wrongly exclude the omitted-field case.

An internal Chroma document ID exists as an implementation detail of the vector store client but is not a meaningful domain field, so it is not listed above. The embedding vector is likewise not a domain field: the Gemini embedding API generates it (at ingestion time for a chunk's `content`, and at query time for the student's question — `research.md` §3), and Chroma stores it internally alongside the document. Nothing in the application code needs to read or reason about the vector itself.

**Validation**: `content` non-empty; `url` must match an entry in the approved-source manifest (`research.md` §6) — this is what enforces "approved PNW sources only" (FR-002/FR-004). `SourceChunk` has no domain ID field of its own. Idempotent re-ingestion is a store-wrapper implementation detail, not a domain concern: before writing a source's newly parsed chunks, the ingestion pipeline first deletes any chunks already stored for that `url`, then inserts the new ones, each assigned its own internal Chroma document ID derived from `url` + chunk index (e.g. `f"{url}#{i}"`) — so multiple chunks from the same source get distinct Chroma IDs rather than all colliding on the `url` itself.

**No freshness field**: There is no persisted `freshnessIndicator`. Explicit currency signals (a visible "last updated" date, a stated academic year/term, a PDF's document date) are preserved as part of `content`/`structureContext` like any other source text — they are not extracted into a separate generated field. Instead, `backend/app/grounding.py` looks for explicit old-date/old-term evidence in *retrieved* content at query time, only when the question is *time-sensitive* — a question is time-sensitive when its retrieved chunks carry an `academicTerm` value or the question matches a deadline/date topic (e.g., "deadline", "due", "when is", "last day to"); see `tasks.md` T034 for the exact heuristic: if the only relevant evidence is clearly old and no current/newer evidence also supports the answer, grounding returns `cannot_answer` (`reason = "insufficient_source_info"`); if newer evidence is also retrieved and used, the uncertainty about the older source is instead surfaced in prose in the answer's `explanation` (`generation.py`). The system never invents a freshness classification when currency can't be established — see `research.md` §5.

**Why one entity, not several**: FR-016 only requires that a prerequisite is never attributed to the wrong course *when answering* — `courseName` on the chunk that documents it achieves this without a relational join or a separate prerequisites field. FR-009's program/student-level clarification only needs `programName`/`studentLevel` as filterable identifiers, not a duplicated description field. Collapsing `Source` to `SourceChunk` with only fields the ingestion pipeline can reliably populate keeps the storage model to what the approved-source corpus can actually support — see `research.md` §5 for the full rationale.

## Transient entities (request/response only — not persisted)

These map directly to the shapes in `contracts/query-api.md`. They exist only for the duration of one HTTP request/response and are defined as Pydantic models in `backend/app/models.py`.

### QueryRequest

| Field | Type | Notes |
|---|---|---|
| `text` | string | Raw natural-language question from the request body; MUST be non-empty after trimming (enforced by a standard Pydantic field constraint, not custom validation logic) |
| `context.campus` | `"hammond" \| "westville"`, optional | Supplied by the client when answering a prior `clarification_needed` response, or when the question text itself names a campus |
| `context.academicTerm` | string, optional | Supplied by the client when answering a prior `clarification_needed` response about term |
| `context.program` | string, optional | Supplied by the client when answering a prior `clarification_needed` response with `missingContext = "program"`; matched against `SourceChunk.programName` |
| `context.studentLevel` | `"undergraduate" \| "graduate"`, optional | Supplied by the client when answering a prior `clarification_needed` response with `missingContext = "student_level"` |

No student-identifying fields exist anywhere in this model (FR-020, FR-024 — no auth/identity captured).

### QueryResponse

Exactly one of three variants, discriminated by `type` — the same vocabulary the API uses (no separate internal "status" naming):

**`answered`** (FR-003; requires the sufficiency AND no-material-conflict checks in `grounding.py` to have passed)

| Field | Type | Notes |
|---|---|---|
| `directAnswer` | string | The direct answer (FR-003) |
| `explanation` | string | Plain-language elaboration (FR-019); also where uncertainty about an explicitly *older* source is expressed in prose (FR-018), but only when current/newer evidence is also retrieved and used for the answer. A *material* conflict between approved sources on the fact needed to answer is never expressed this way — `grounding.py` catches it before generation runs and the response is `cannot_answer` (`reason = "conflicting_sources"`) instead (FR-017). When a question spans multiple sub-topics and only some are answerable, this is also where the unanswerable part is named and referred in prose — there is no separate structured referral field on `answered` (`officeName` exists only on `cannot_answer`) |
| `sources` | `{title, url}[]` | MUST be non-empty (FR-006) — just enough to cite and link the supporting source(s); no separate metadata is echoed back |

**`clarification_needed`** (FR-009)

| Field | Type | Notes |
|---|---|---|
| `promptText` | string | The clarifying question shown to the student |
| `missingContext` | `"campus" \| "program" \| "academic_term" \| "student_level"` | What's missing |
| `options` | string[], optional | A finite option list when one exists — `["Hammond", "Westville"]` for `campus`, `["Undergraduate", "Graduate"]` for `student_level`; omitted for `academic_term` and `program`, which have an open/corpus-dependent set of values and are answered as free text instead |

The student's answer becomes the `context` on their *next* `QueryRequest` — there is no server-side "pending clarification" record to look up.

**`cannot_answer`** (FR-007, FR-008)

| Field | Type | Notes |
|---|---|---|
| `message` | string | States the limitation; never a fabricated guess |
| `reason` | `"insufficient_source_info" \| "private_data_required" \| "conflicting_sources" \| "out_of_scope_topic"` | Why the referral is being made — maps to FR-007/FR-008/FR-017/edge cases |
| `officeName` | string | The appropriate PNW office/department/advisor to contact (FR-008) |

**Validation** (enforced in `backend/app/grounding.py`, not by a database constraint):
- `answered` requires `sources` non-empty.
- `cannot_answer` requires `officeName` non-empty.
- `clarification_needed` never includes `directAnswer`.

## Relationships summary

- One `QueryRequest` produces exactly one `QueryResponse` variant — computed fresh each request, nothing stored server-side.
- An `answered` response references 1..* `SourceChunk` records (by citation — title/url only, not the full persisted record).
- `SourceChunk.courseName`/`content` encode course↔prerequisite attribution directly on the chunk (no separate `Course`/`Program`/prerequisites entity).
- A source's child page or attached document is its own `SourceChunk` row(s), included because the approved-source manifest lists it explicitly (`research.md` §6) — there is no `parentDocumentUrl` linkage field; nothing in the design needs to walk that relationship programmatically.

## State transitions

There is no server-side entity lifecycle to manage: each `POST /api/query` request is handled statelessly from `QueryRequest` → `QueryResponse` using only the request's own `text`/`context` and the persisted `SourceChunk` corpus. Multi-turn disambiguation (FR-009) is achieved by the client re-submitting a new `QueryRequest` with `context` filled in from the prior `clarification_needed` response — not by mutating stored state.
