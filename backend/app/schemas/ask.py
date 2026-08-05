"""`POST /api/v1/ask` — the core endpoint (API_CONTRACT §1.1).

The agent service returns a *flat* situation report; this is the *nested* wire
shape the contract specifies. The translation between them is the gateway's job
and lives in `app/services/mapping.py`.
"""

from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import (
    Citation,
    Confidence,
    OwningAgent,
    PriorityClass,
    RoleLens,
    SectionStatus,
    SectionTypeName,
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: UUID | None = None
    document_ids: list[UUID] | None = None
    # Initial render only — the toggle re-renders client-side and never
    # re-calls this endpoint.
    role_lens: RoleLens | None = None

    @field_validator("question")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped


class Priority(BaseModel):
    """`citation` is never null for a W-class — an uncited severity is an
    ungrounded model opinion, so the mapper downgrades rather than invent one."""

    class_: PriorityClass = Field(default="informational", alias="class")
    label: str = "OBSERVATION"
    reason: str = ""
    citation: str | None = None
    page: int | None = None

    model_config = {"populate_by_name": True}


class ConfidenceBlock(BaseModel):
    level: Confidence = "insufficient"
    reason: str = ""
    groundedness: int = Field(default=0, ge=0, le=100)


class ReportSection(BaseModel):
    """One specialist-owned content section.

    Section independence is a hard guarantee: `status != "filled"` is a normal
    path, not an edge case, and `empty_reason` is non-null whenever it happens.
    """

    section_type: SectionTypeName
    owning_agent: OwningAgent = "orchestrator"
    status: SectionStatus = "empty"
    empty_reason: str | None = None
    content: str = ""
    claim_count: int = 0
    supported_claim_count: int = 0
    duration_ms: int = 0
    display_order: int = 0


class ConflictPosition(BaseModel):
    record_id: str
    claim: str = ""
    evidence_quality: str = ""
    reliability_limitation: str = ""


class Conflict(BaseModel):
    """Positions are never merged into a single view and no cause is declared."""

    record_ids: list[str] = Field(default_factory=list)
    conflict_nature: str = ""
    positions: list[ConflictPosition] = Field(default_factory=list)
    resolution_recommendation: str = ""


class SituationReport(BaseModel):
    priority: Priority = Field(default_factory=Priority)
    # Drives the map — there is no separate endpoint. Empty = map stays idle.
    affected_region_ids: list[str] = Field(default_factory=list)
    assembly_mode: str = "sitrep"
    sections: list[ReportSection] = Field(default_factory=list)
    confidence: ConfidenceBlock = Field(default_factory=ConfidenceBlock)
    conflicts: list[Conflict] = Field(default_factory=list)
    # A partial report is a success, not an error.
    was_partial: bool = False


class ClosestMatch(BaseModel):
    record_id: str = ""
    title: str = ""
    relevance_score: float = 0.0
    page: int | None = None


class InsufficientEvidence(BaseModel):
    """§1.4. Non-null **only** when `has_sufficient_evidence` is false.

    `message` is the brief's mandated sentence, verbatim. Do not reword,
    truncate, or template over it — it is carried through from the agent
    untouched rather than rebuilt here.
    """

    banner: str = ""
    message: str = ""
    searched_scope: str = ""
    closest_matches: list[ClosestMatch] = Field(default_factory=list)
    what_would_resolve: str = ""


class AskResponse(BaseModel):
    answer_id: UUID
    conversation_id: UUID
    situation_report: SituationReport
    insufficient_evidence: InsufficientEvidence | None = None
    citations: list[Citation] = Field(default_factory=list)
    has_sufficient_evidence: bool = True
    llm_call_count: int = 0
    latency_ms: int = 0
