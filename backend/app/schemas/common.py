"""Shared schema pieces: the error envelope, timestamps, citations, paging.

Every model here mirrors docs/API_CONTRACT.md. The contract is the source of
truth; these are its implementation.
"""

from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, PlainSerializer


def _iso_utc(value: datetime) -> str:
    """ISO 8601 UTC with a trailing Z — `2026-08-05T14:23:00Z`, as the contract states."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


UtcDatetime = Annotated[datetime, PlainSerializer(_iso_utc, return_type=str)]

Confidence = Literal["high", "moderate", "low", "insufficient"]
DocumentStatus = Literal["pending", "indexing", "indexed", "failed"]
ActionType = Literal["flag_invoice", "draft_email", "create_task"]
ActionStatus = Literal["proposed", "approved", "rejected", "completed"]

RoleLens = Literal["guardian", "researcher", "citizen"]
PriorityClass = Literal["W1", "W2", "W3", "W4", "informational"]
SectionType = Literal["affected_species", "likely_causes", "recommended_actions"]
SectionStatus = Literal["filled", "empty", "timed_out", "not_applicable"]
OwningAgent = Literal[
    "marine_life_protector", "incident_investigator", "emergency_responder", "orchestrator"
]
AssemblyMode = Literal["sitrep", "focused", "compare", "single_agent_fallback"]

# The corpus's own five-value taxonomy, carried verbatim (corpus p.2 instructs
# that RAG applications "should preserve these labels"). Typed as a plain `str`
# on the wire deliberately: an unrecognised label from the agent service must
# reach the UI, not 500 the gateway.
EVIDENCE_QUALITIES = (
    "verified_observation",
    "community_tradition",
    "provisional_interpretation",
    "modeled_estimate",
    "disputed_report",
)

# Substituted when the agent cites a document the gateway cannot resolve. Keeps
# the citation — and the record ID marker in the section text — rather than
# dropping evidence the report already refers to.
UNKNOWN_DOCUMENT_ID = UUID("00000000-0000-4000-8000-000000000000")
UNKNOWN_DOCUMENT_NAME = "(document unavailable)"


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorEnvelope(BaseModel):
    """Documented here so it appears in the OpenAPI docs at /docs."""

    error: ErrorDetail


class Citation(BaseModel):
    """A source card (§1.1). `document_name` is joined on by the backend, not the agent.

    `record_id` is what the section text actually cites — `[INC-005]`, `[FAU-003 p.13]`.
    `marker` survives only as a stable integer for ordering the source cards.
    """

    marker: int
    document_id: UUID
    document_name: str
    chunk_id: str | None = None
    record_id: str
    record_type: str
    title: str = ""
    chapter: str = ""
    section: str = ""
    page: int | None = None
    region_id: str | None = None
    excerpt: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    rerank_score: float | None = None
    evidence_quality: str
    risk_level: str | None = None
    record_date: str | None = None
    section_types: list[str] = Field(default_factory=list)


class ActionCitation(BaseModel):
    """The trimmed citation carried on a persisted action (§1.4)."""

    document_id: UUID
    document_name: str
    page: int | None = None
    excerpt: str


class Paged(BaseModel):
    total: int
    limit: int
    offset: int
