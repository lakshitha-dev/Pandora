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

# `moderate`, not `medium` — the contract's wording. The agent emits "medium",
# so services/mapping.py normalises on the way out. One place, not scattered.
Confidence = Literal["high", "moderate", "low", "insufficient"]
DocumentStatus = Literal["pending", "indexing", "indexed", "failed"]
PriorityClass = Literal["W1", "W2", "W3", "W4", "informational"]
RoleLens = Literal["guardian", "researcher", "citizen"]
SectionStatus = Literal["filled", "empty", "timed_out", "not_applicable"]
SectionTypeName = Literal["affected_species", "likely_causes", "recommended_actions"]
OwningAgent = Literal[
    "marine_life_protector", "incident_investigator", "emergency_responder", "orchestrator"
]


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorEnvelope(BaseModel):
    """Documented here so it appears in the OpenAPI docs at /docs."""

    error: ErrorDetail


class Citation(BaseModel):
    """A source card (§1.1). `document_name` is joined on by the backend, not the agent.

    `record_id` is what the report text actually cites — markers in the content
    are record IDs (`[INC-005]`), not integers, so a marker the model invented
    cannot resolve. `marker` survives only as a stable integer for ordering.
    """

    marker: int
    document_id: UUID
    document_name: str
    chunk_id: str | None = None
    record_id: str = ""
    record_type: str = ""
    title: str = ""
    chapter: str = ""
    section: str | None = None
    page: int | None = None
    region_id: str | None = None
    excerpt: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    rerank_score: float | None = None
    # The corpus's own five-value taxonomy, carried verbatim — the corpus
    # instructs that RAG applications preserve these labels.
    evidence_quality: str = ""
    risk_level: str | None = None
    record_date: str | None = None
    section_types: list[str] = Field(default_factory=list)


class Paged(BaseModel):
    total: int
    limit: int
    offset: int
