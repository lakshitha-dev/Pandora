"""`POST /api/v1/ask` — the core endpoint (API_CONTRACT §1.1)."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ActionType, Citation, Confidence


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None
    document_ids: list[UUID] | None = None

    @field_validator("question")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped


class SuggestedAction(BaseModel):
    type: ActionType
    title: str
    rationale: str
    payload: dict[str, Any]
    supporting_citations: list[int] = Field(default_factory=list)


class AskResponse(BaseModel):
    answer_id: UUID
    conversation_id: UUID
    answer: str
    citations: list[Citation]
    # Null on most queries. The common path, not the edge case.
    suggested_action: SuggestedAction | None = None
    confidence: Confidence
    has_sufficient_evidence: bool
    latency_ms: int
