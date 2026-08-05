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

Confidence = Literal["high", "medium", "low", "insufficient"]
DocumentStatus = Literal["pending", "indexing", "indexed", "failed"]
ActionType = Literal["flag_invoice", "draft_email", "create_task"]
ActionStatus = Literal["proposed", "approved", "rejected", "completed"]


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorEnvelope(BaseModel):
    """Documented here so it appears in the OpenAPI docs at /docs."""

    error: ErrorDetail


class Citation(BaseModel):
    """A source card. `document_name` is joined on by the backend, not the agent."""

    marker: int
    document_id: UUID
    document_name: str
    page: int | None = None
    section: str | None = None
    excerpt: str
    relevance_score: float = Field(ge=0.0, le=1.0)


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
