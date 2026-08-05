"""`POST /api/v1/ask` — the core endpoint (API_CONTRACT §1.1)."""

from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import Citation, RoleLens
from app.schemas.situation_report import InsufficientEvidence, SituationReport


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None
    # null = the whole index, including the preloaded corpus.
    document_ids: list[UUID] | None = None
    # Initial render only. The lens toggle re-renders client-side and never
    # re-calls this endpoint, so the gateway records the caller's starting lens
    # and nothing downstream branches on it.
    role_lens: RoleLens | None = None

    @field_validator("question")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped


class AskResponse(BaseModel):
    answer_id: UUID
    conversation_id: UUID
    # Always present. Every query produces a report — including a refusal.
    situation_report: SituationReport
    # Non-null only when `has_sufficient_evidence` is false.
    insufficient_evidence: InsufficientEvidence | None = None
    # Deduplicated union across all sections. May be empty on a refusal.
    citations: list[Citation] = Field(default_factory=list)
    has_sufficient_evidence: bool = True
    llm_call_count: int = 0
    latency_ms: int = 0
