"""`GET /api/v1/situation-reports` — past reports (API_CONTRACT §1.5).

Backs `/app/investigations`. The detail route also carries `trace`, so the
orchestration rail can **replay** a stored run: demo insurance for when the
live network stalls.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.ask import AskResponse
from app.schemas.common import Confidence, PriorityClass, UtcDatetime


class SituationReportSummary(BaseModel):
    """List-row projection. The scalar columns behind these are indexed, so the
    §1.5 filters never scan the stored JSON."""

    answer_id: UUID
    question: str
    priority_class: PriorityClass = "informational"
    assembly_mode: str = "sitrep"
    confidence_level: Confidence = "insufficient"
    affected_region_ids: list[str] = Field(default_factory=list)
    citation_count: int = 0
    had_conflict: bool = False
    was_insufficient: bool = False
    was_partial: bool = False
    created_at: UtcDatetime


class SituationReportListResponse(BaseModel):
    reports: list[SituationReportSummary] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class TraceStep(BaseModel):
    step_type: str
    sequence_number: int
    duration_ms: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)


class SituationReportDetail(AskResponse):
    """The full §1.1 body plus the persisted trace, in `sequence_number` order."""

    trace: list[TraceStep] = Field(default_factory=list)
