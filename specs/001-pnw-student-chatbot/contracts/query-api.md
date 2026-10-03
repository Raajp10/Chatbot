# API Contract: Chat Query Endpoint

**Feature**: 001-pnw-student-chatbot | **Date**: 2026-09-19 (re-simplified)

This is the single external interface the application exposes: the React chat UI calls it, and it is the seam for backend contract tests (`backend/tests/contract/`, using FastAPI's `TestClient`). No other external-facing API is defined for this version (no auth endpoints — FR-024; no separate embed/widget API — FR-026). Served by FastAPI at a local address (e.g., `http://localhost:8000`) during development; the frontend dev server (e.g., `http://localhost:5173`) reaches it via CORS.

The audience disclaimer (FR-024) is rendered statically in the React frontend, not returned by this API — see `research.md` §7.

## `POST /api/query`

Submits a student question (optionally with context resolved from a prior turn) and receives a grounded answer, a clarification request, or a referral. The server is stateless across requests — see `data-model.md` — so the client is responsible for sending back any previously resolved `context`.

### Request

```json
{
  "text": "string, required — the student's natural-language question, non-empty after trimming",
  "context": {
    "campus": "hammond | westville | null, optional — set when answering a prior clarification_needed response",
    "academicTerm": "string | null, optional — set when answering a prior clarification_needed response",
    "program": "string | null, optional — set when answering a prior clarification_needed response with missingContext=program; matched against SourceChunk.programName",
    "studentLevel": "undergraduate | graduate | null, optional — set when answering a prior clarification_needed response with missingContext=student_level"
  }
}
```

**Validation**: `text` non-emptiness (after trimming) is enforced by a standard Pydantic field constraint on the `QueryRequest` model — no custom validation layer. `context` fields are only meaningful as an answer to a prior `clarification_needed` response; the server does not require the client to send them otherwise.

### Response — `200 OK`

Exactly one of the three `type` variants below is returned, matching `QueryResponse` in `data-model.md`.

```json
{
  "type": "answered",
  "directAnswer": "string",
  "explanation": "string",
  "sources": [
    { "title": "string", "url": "string" }
  ]
}
```

`sources` MUST be non-empty (FR-006). Uncertainty about an explicitly *older* source — when current/newer evidence is also retrieved and used — is expressed in prose inside `explanation` (e.g., "the source lists a Fall 2025 deadline; this may not reflect the current term"), not as a separate structured field. This is the only case `answered` may carry any uncertainty: a *material* conflict between approved sources on the fact needed to answer the question, or a time-sensitive question where the only relevant evidence is explicitly old with no current/newer evidence available, MUST NOT be returned as `answered` — the server MUST return `cannot_answer` instead (`reason = "conflicting_sources"` for a material conflict; `reason = "insufficient_source_info"` for explicitly-old-only evidence on a time-sensitive question). An `answered` response is only ever produced when grounding is sufficient and unconflicted.

```json
{
  "type": "clarification_needed",
  "promptText": "string",
  "missingContext": "campus | program | academic_term | student_level",
  "options": ["string", "..."]
}
```

`options` is a finite list for `campus` (`["Hammond", "Westville"]`) and `student_level` (`["Undergraduate", "Graduate"]`); it is omitted for `academic_term` and `program`, since both have an open, corpus-dependent set of values — the client should render a free-text input for those two and send the answer back as `context.academicTerm` / `context.program` on the next request.

```json
{
  "type": "cannot_answer",
  "message": "string — states the limitation, never a fabricated guess",
  "reason": "insufficient_source_info | private_data_required | conflicting_sources | out_of_scope_topic",
  "officeName": "string"
}
```

### Response — `422 Unprocessable Entity`

Standard FastAPI/Pydantic validation response, returned automatically when `text` is empty/missing/malformed — no custom error body is defined beyond FastAPI's default validation error shape.

### Response — `503 Service Unavailable`

Returned when the backend cannot complete the request because the Gemini API is unavailable, its free-tier quota/rate limit has been hit, or the PostgreSQL/pgvector database cannot be reached. Body: `{ "error": "string" }`. The frontend shows a generic "please try again shortly" message; the client does not need a machine-readable retry time for this v1 (see `research.md` §10).

## Contract test coverage (for `/speckit-tasks` to schedule)

- `answered` responses always include ≥1 `sources` entry, each with `title` and `url` (enforces FR-006/data-model validation).
- `clarification_needed` responses never include `directAnswer`.
- `cannot_answer` responses always include a non-empty `officeName`.
- Empty `text` → `422` (standard Pydantic validation, not a custom body).
- A campus-ambiguous question → `clarification_needed` with `missingContext = "campus"` and `options = ["Hammond", "Westville"]`.
- A program-requirements question that doesn't name a program, where the corpus covers multiple programs → `clarification_needed` with `missingContext = "program"` and `options` omitted.
- A question whose relevant content differs by academic level and doesn't specify one → `clarification_needed` with `missingContext = "student_level"` and `options = ["Undergraduate", "Graduate"]`.
- A question whose only relevant retrieved sources materially conflict on the fact needed to answer → `cannot_answer` with `reason = "conflicting_sources"` and a non-empty `officeName` — never `answered`.
- A time-sensitive question drawing only on a source that is explicitly old, with no current/newer evidence retrieved → `cannot_answer` (`reason = "insufficient_source_info"`); the same question when newer evidence is also retrieved and used → `answered` with `explanation` noting the older source's possible staleness.
- A question naming an explicit `academicTerm` (in `context` or the question text) → retrieval is restricted/boosted to that term, and the returned `sources`/`explanation` do not draw on a conflicting different term.
