"""Pydantic models mirroring docs/API_CONTRACT.md Part 2 (internal API).

The contract file is the source of truth; these are its implementation. When
the contract changes, both this and the gateway's models change.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────


class SectionType(str, Enum):
    """The six fixed Situation Report sections (SOLUTION.md §2.1)."""

    PRIORITY = "priority"
    AFFECTED_SPECIES = "affected_species"
    LIKELY_CAUSES = "likely_causes"
    RECOMMENDED_ACTIONS = "recommended_actions"
    SOURCES = "sources"
    CONFIDENCE = "confidence"


class SectionStatus(str, Enum):
    FILLED = "filled"
    EMPTY = "empty"
    TIMED_OUT = "timed_out"
    NOT_APPLICABLE = "not_applicable"


class PriorityClass(str, Enum):
    """The corpus's own W1–W4 water incident scale (§4.5)."""

    W1 = "W1"
    W2 = "W2"
    W3 = "W3"
    W4 = "W4"
    INFORMATIONAL = "Informational"


# ─────────────────────────────────────────────────────────────────────────
# /rag/ingest
# ─────────────────────────────────────────────────────────────────────────


class IngestRequest(BaseModel):
    document_id: str
    file_name: str
    content_type: str
    content_base64: str


class IngestResponse(BaseModel):
    document_id: str
    status: Literal["indexed", "failed"]
    chunk_count: int = 0
    record_count: int = 0
    page_count: int | None = None
    chunking_mode: Literal["record_aware", "narrative"] = "narrative"
    error_message: str | None = None
    duration_ms: int = 0


# ─────────────────────────────────────────────────────────────────────────
# Shared response pieces
# ─────────────────────────────────────────────────────────────────────────


class Citation(BaseModel):
    marker: int
    document_id: str
    chunk_id: str
    record_id: str
    record_type: str
    title: str = ""
    chapter: str = ""
    section: str = ""
    page: int | None = None
    region_id: str | None = None
    excerpt: str
    relevance_score: float
    rerank_score: float | None = None
    evidence_quality: str
    risk_level: str | None = None
    record_date: str | None = None


class GroundingRuleResult(BaseModel):
    number: int
    name: str
    passed: bool
    detail: str


class Grounding(BaseModel):
    groundedness: int = Field(ge=0, le=100)
    rules: list[GroundingRuleResult] = Field(default_factory=list)
    unsupported_sentences: list[str] = Field(default_factory=list)


class ConflictPosition(BaseModel):
    """One side of a disagreement, carrying its own reliability limitation.

    Positions are never merged into a single view. §14.3 of the corpus is a
    planted trap with a stated expected answer: present every position, name
    what limits each, and decline to pick a winner.
    """

    record_id: str
    claim: str
    evidence_quality: str = ""
    reliability_limitation: str = ""


class Conflict(BaseModel):
    record_ids: list[str]
    nature: str
    reliability_limitation: str
    positions: list[ConflictPosition] = Field(default_factory=list)
    resolution_recommendation: str = ""


# Fixed display order of the six Situation Report sections (SOLUTION.md §2.1).
# Priority, Sources, and Confidence are the orchestrator's own top-level
# fields rather than rows in `sections`, so only 2-4 are ever emitted here.
SECTION_DISPLAY_ORDER: dict[SectionType, int] = {
    SectionType.PRIORITY: 1,
    SectionType.AFFECTED_SPECIES: 2,
    SectionType.LIKELY_CAUSES: 3,
    SectionType.RECOMMENDED_ACTIONS: 4,
    SectionType.SOURCES: 5,
    SectionType.CONFIDENCE: 6,
}


class ReportSection(BaseModel):
    section_type: SectionType
    status: SectionStatus
    empty_reason: str | None = None
    content: str = ""
    claim_count: int = 0
    supported_claim_count: int = 0
    owning_agent: str = "single_agent"
    duration_ms: int = 0
    display_order: int = 0


# ─────────────────────────────────────────────────────────────────────────
# /rag/query
# ─────────────────────────────────────────────────────────────────────────


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[str] | None = None
    top_k: int | None = None
    record_type_filter: list[str] | None = None
    region_id_filter: list[str] | None = None
    section_type: SectionType | None = None
    conversation_history: list[ConversationTurn] = Field(default_factory=list)


class QueryResponse(BaseModel):
    sections: list[ReportSection] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    grounding: Grounding
    conflicts: list[Conflict] = Field(default_factory=list)
    has_sufficient_evidence: bool = True
    retrieved_chunk_count: int = 0
    top_rerank_score: float = 0.0
    rerank_mode: Literal["llm", "semantic", "none"] = "none"
    duration_ms: int = 0


# ─────────────────────────────────────────────────────────────────────────
# /agent/sitrep
# ─────────────────────────────────────────────────────────────────────────


class SitrepRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    document_ids: list[str] | None = None
    mode: Literal["sitrep", "focused", "compare"] | None = None
    conversation_history: list[ConversationTurn] = Field(default_factory=list)


class SituationReport(BaseModel):
    priority_class: PriorityClass = PriorityClass.INFORMATIONAL
    priority_reason: str = ""
    priority_citation: str = ""
    priority_label: str = "INFORMATIONAL"
    priority_page: int | None = None
    affected_region_ids: list[str] = Field(default_factory=list)
    assembly_mode: str = "single_agent"
    confidence_level: str = "medium"
    confidence_reason: str = ""
    was_partial: bool = False
    sections: list[ReportSection] = Field(default_factory=list)


class ClosestMatch(BaseModel):
    """A sub-threshold hit. Shown clearly labelled, never presented as an answer."""

    record_id: str
    title: str = ""
    relevance_score: float = 0.0
    page: int | None = None


class InsufficientEvidence(BaseModel):
    """The honesty flip, structured (API_CONTRACT §1.4).

    `message` is the brief's mandated sentence, carried verbatim from
    `INSUFFICIENT_EVIDENCE_MESSAGE`. It is a 20-mark criterion: never reword,
    truncate, or template over it. The actionable headline lives in `banner`
    so the command-center framing costs nothing from the mandated wording.
    """

    banner: str = "⚠ Insufficient Evidence — Recommend Field Investigation"
    message: str
    searched_scope: str = ""
    closest_matches: list[ClosestMatch] = Field(default_factory=list)
    what_would_resolve: str = ""


class SitrepResponse(BaseModel):
    situation_report: SituationReport
    citations: list[Citation] = Field(default_factory=list)
    grounding: Grounding
    conflicts: list[Conflict] = Field(default_factory=list)
    has_sufficient_evidence: bool = True
    insufficient_evidence: InsufficientEvidence | None = None
    llm_call_count: int = 0
    duration_ms: int = 0
    top_rerank_score: float = 0.0


# ─────────────────────────────────────────────────────────────────────────
# /rag/incidents — docs/API_CONTRACT.md §1.6
# ─────────────────────────────────────────────────────────────────────────


class Incident(BaseModel):
    """One incident record, projected straight from index metadata.

    No retrieval scoring and no LLM call — §1.6 is a filtered listing of
    fields the index already carries, so it stays cheap enough to page.
    """

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
    total: int = 0
    limit: int = 50
    offset: int = 0


# ─────────────────────────────────────────────────────────────────────────
# Orchestration trace (SSE) — docs/API_CONTRACT.md §1.2
# ─────────────────────────────────────────────────────────────────────────


class TraceEvent(BaseModel):
    """One orchestration step, streamed as it happens.

    New step types are additive only — never removed, never renamed. Three
    people build against this schema simultaneously, and an unknown
    step_type must be ignored by the client rather than crash it.
    """

    step_type: str
    sequence_number: int
    duration_ms: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────
# /health
# ─────────────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    search_index_reachable: bool
    llm_reachable: bool
    corpus_indexed: bool
    corpus_chunk_count: int = 0
    corpus_record_count: int = 0
    rerank_mode: Literal["llm", "semantic", "none"] = "none"
    version: str = "0.1.0"


# ─────────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────────


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
