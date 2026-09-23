"""POST /api/query route — the one place that owns the orchestration order. Implemented in T016/T020."""

from fastapi import APIRouter

from app.models import QueryRequest, QueryResponse

router = APIRouter()


@router.post("/api/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    """The single authoritative end-to-end orchestration order for this handler (T020).

    Every later task that adds a piece of the pipeline (T030, T035, T042, T054, T061)
    implements its own logic into this order and MUST NOT define a conflicting order of
    its own. `clarification.py` (T040/T053/T060) owns exactly two functions used at two
    different points below: `extract_explicit_context(question_text, request_context)` and
    `find_missing_context(retrieved_chunks, resolved_context)` — it is still one module,
    not two.

    The order — matching the Architecture diagram in plan.md — is:
      1. Validate the request (QueryRequest's Pydantic validation; a 422 is returned
         automatically on failure).
      2. Run the private-data/personalized-records check (grounding.py). If triggered,
         return cannot_answer with officeName set WITHOUT calling retrieval.
      3. Call clarification.extract_explicit_context(text, context) to resolve as much of
         campus/program/student_level/academic_term as possible from the request's
         context and/or explicit mentions in the question text. This does not yet decide
         whether anything is missing — only what's already resolvable.
      4. Retrieve relevant SourceChunks, applying: (i) whatever resolved-context metadata
         filters step 3 supports, and (ii) independently of step 3, a raw-text courseName
         boost whenever the question names a specific course.
      5. Call clarification.find_missing_context(retrieved_chunks, resolved_context) to
         check, using the chunks actually retrieved, whether campus/program/student_level/
         academic_term is still required and unresolved — checked in this priority order
         when more than one could apply: (a) campus, (b) program, (c) student_level,
         (d) academic_term.
      6. If context is still missing, return exactly one clarification_needed response for
         the first applicable item in that priority order — do not proceed further.
      7. Otherwise, run the grounding/fail-safe checks (grounding.py): (a) insufficient
         grounding, (b) a material conflict between retrieved sources on the fact needed to
         answer — this ALWAYS returns cannot_answer (reason = "conflicting_sources");
         generation is never called to pick a side, (c) out-of-scope, (d) explicit-outdated-
         evidence for time-sensitive questions. If any check fails, return cannot_answer with
         officeName set — do not proceed further.
      8. Otherwise, call grounded Gemini generation.
      9. Validate that the answered result has non-empty sources before returning
         (data-model.md validation).
      10. Return the final response.

    Foundational-phase note: this module currently only wires the route and documents the
    order above. The pipeline itself (grounding.py, clarification.py, retrieval filtering,
    generation) is implemented incrementally by the user-story tasks listed above, starting
    at T030 (User Story 1).
    """
    raise NotImplementedError(
        "POST /api/query pipeline is implemented incrementally starting at T030 (User Story 1)"
    )
