"""Pydantic request/response models: QueryRequest, QueryResponse (answered / clarification_needed / cannot_answer). Implemented in T012."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

Campus = Literal["hammond", "westville"]
StudentLevel = Literal["undergraduate", "graduate"]
MissingContext = Literal["campus", "program", "academic_term", "student_level"]
CannotAnswerReason = Literal[
    "insufficient_source_info",
    "private_data_required",
    "conflicting_sources",
    "out_of_scope_topic",
]


class QueryContext(BaseModel):
    campus: Campus | None = None
    academicTerm: str | None = None
    program: str | None = None
    studentLevel: StudentLevel | None = None


class QueryRequest(BaseModel):
    text: NonEmptyStr
    context: QueryContext | None = None


class SourceCitation(BaseModel):
    title: str
    url: str


class AnsweredResponse(BaseModel):
    type: Literal["answered"] = "answered"
    directAnswer: str
    explanation: str
    sources: Annotated[list[SourceCitation], Field(min_length=1)]


class ClarificationNeededResponse(BaseModel):
    type: Literal["clarification_needed"] = "clarification_needed"
    promptText: str
    missingContext: MissingContext
    options: list[str] | None = None


class CannotAnswerResponse(BaseModel):
    type: Literal["cannot_answer"] = "cannot_answer"
    message: str
    reason: CannotAnswerReason
    officeName: NonEmptyStr


QueryResponse = Annotated[
    AnsweredResponse | ClarificationNeededResponse | CannotAnswerResponse,
    Field(discriminator="type"),
]
