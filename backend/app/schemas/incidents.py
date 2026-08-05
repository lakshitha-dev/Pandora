"""`GET /api/v1/incidents` — the incident register (API_CONTRACT §1.6).

A filtered projection of metadata already in the index: no new retrieval work
and no LLM call. Selecting one pre-fills the Command Center question box, so
this is a shortcut into `/app`, not a separate reader.
"""

from typing import Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["low", "medium", "high", "critical"]


class Incident(BaseModel):
    record_id: str
    title: str = ""
    region_id: str | None = None
    region_name: str | None = None
    risk_level: str | None = None
    chapter: str = ""
    page: int | None = None
    summary_excerpt: str = ""
    evidence_quality: str = ""


class IncidentListResponse(BaseModel):
    incidents: list[Incident] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
