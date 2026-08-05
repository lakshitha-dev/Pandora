"""Internal API shapes — the agent service (API_CONTRACT Part 2).

These are *our* mirror of Lakshitha's contract. Defined twice on purpose: a shared
package would cost packaging setup and a coordinated redeploy for a handful of
small classes. When the contract changes, both sides change.

Response models are deliberately lenient (`extra="allow"`, wide optionals) so an
extra field from the agent service never 500s the gateway.

**`document_id` is a `str` here, not a `UUID`.** The pre-indexed corpus carries
the sentinel `"pandora-corpus"` (agent/app/ingestion/parse.py), not a UUID, and
typing this field as `UUID` would reject every corpus citation. The gateway maps
the sentinel onto the seeded corpus row's real UUID when it joins names, so the
public wire in Part 1 still speaks UUIDs as the contract shows.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


# --- Shared response pieces ---------------------------------------------------


class RagCitation(BaseModel):
    """No `document_name` — the agent service stays free of app-DB coupling."""

    model_config = ConfigDict(extra="allow")

    marker: int
    document_id: str
    chunk_id: str | None = None
    record_id: str = ""
    record_type: str = ""
    title: str = ""
    chapter: str = ""
    section: str = ""
    page: int | None = None
    region_id: str | None = None
    excerpt: str = ""
    relevance_score: float = 0.0
    rerank_score: float | None = None
    evidence_quality: str = ""
    risk_level: str | None = None
    record_date: str | None = None


class GroundingRuleResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    number: int = 0
    name: str = ""
    passed: bool = False
    detail: str = ""


class Grounding(BaseModel):
    model_config = ConfigDict(extra="allow")

    groundedness: int = 0
    rules: list[GroundingRuleResult] = Field(default_factory=list)
    unsupported_sentences: list[str] = Field(default_factory=list)


class ConflictPosition(BaseModel):
    model_config = ConfigDict(extra="allow")

    record_id: str
    claim: str = ""
    evidence_quality: str = ""
    reliability_limitation: str = ""


class Conflict(BaseModel):
    model_config = ConfigDict(extra="allow")

    record_ids: list[str] = Field(default_factory=list)
    nature: str = ""
    reliability_limitation: str = ""
    positions: list[ConflictPosition] = Field(default_factory=list)
    resolution_recommendation: str = ""


class RagReportSection(BaseModel):
    model_config = ConfigDict(extra="allow")

    section_type: str
    status: str = "empty"
    empty_reason: str | None = None
    content: str = ""
    claim_count: int = 0
    supported_claim_count: int = 0
    owning_agent: str = "single_agent"
    duration_ms: int = 0
    display_order: int = 0


# --- §2.1 /rag/ingest ---------------------------------------------------------


class RagIngestRequest(BaseModel):
    document_id: str
    file_name: str
    content_type: str
    content_base64: str


class RagIngestResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    document_id: str
    status: Literal["indexed", "failed"]
    chunk_count: int | None = None
    record_count: int | None = None
    page_count: int | None = None
    chunking_mode: str | None = None
    error_message: str | None = None
    duration_ms: int | None = None


# --- §2.2 /rag/query ----------------------------------------------------------


class RagQueryRequest(BaseModel):
    question: str
    document_ids: list[str] | None = None
    top_k: int | None = 6
    record_type_filter: list[str] | None = None
    region_id_filter: list[str] | None = None
    section_type: str | None = None
    conversation_history: list[ConversationTurn] = Field(default_factory=list)


class RagQueryResponse(BaseModel):
    """No top-level `answer` — the agent returns per-section content instead."""

    model_config = ConfigDict(extra="allow")

    sections: list[RagReportSection] = Field(default_factory=list)
    citations: list[RagCitation] = Field(default_factory=list)
    grounding: Grounding = Field(default_factory=Grounding)
    conflicts: list[Conflict] = Field(default_factory=list)
    has_sufficient_evidence: bool = False
    retrieved_chunk_count: int | None = None
    top_rerank_score: float = 0.0
    rerank_mode: str = "none"
    duration_ms: int | None = None


# --- §2.3 /agent/sitrep -------------------------------------------------------


class SitrepRequest(BaseModel):
    question: str
    conversation_id: str | None = None
    document_ids: list[str] | None = None
    mode: Literal["sitrep", "focused", "compare"] | None = None
    conversation_history: list[ConversationTurn] = Field(default_factory=list)


class RagSituationReport(BaseModel):
    """The agent's **flat** shape. The gateway nests it for §1.1 — see services/mapping.py."""

    model_config = ConfigDict(extra="allow")

    priority_class: str = "Informational"
    priority_reason: str = ""
    priority_citation: str = ""
    priority_label: str = "INFORMATIONAL"
    priority_page: int | None = None
    affected_region_ids: list[str] = Field(default_factory=list)
    assembly_mode: str = "single_agent"
    confidence_level: str = "medium"
    confidence_reason: str = ""
    was_partial: bool = False
    sections: list[RagReportSection] = Field(default_factory=list)


class RagClosestMatch(BaseModel):
    model_config = ConfigDict(extra="allow")

    record_id: str = ""
    title: str = ""
    relevance_score: float = 0.0
    page: int | None = None


class RagInsufficientEvidence(BaseModel):
    model_config = ConfigDict(extra="allow")

    banner: str = ""
    message: str = ""
    searched_scope: str = ""
    closest_matches: list[RagClosestMatch] = Field(default_factory=list)
    what_would_resolve: str = ""


class SitrepResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    situation_report: RagSituationReport = Field(default_factory=RagSituationReport)
    citations: list[RagCitation] = Field(default_factory=list)
    grounding: Grounding = Field(default_factory=Grounding)
    conflicts: list[Conflict] = Field(default_factory=list)
    has_sufficient_evidence: bool = True
    insufficient_evidence: RagInsufficientEvidence | None = None
    llm_call_count: int = 0
    duration_ms: int = 0
    top_rerank_score: float = 0.0


# --- §1.6 /rag/incidents ------------------------------------------------------


class RagIncident(BaseModel):
    model_config = ConfigDict(extra="allow")

    record_id: str = ""
    title: str = ""
    region_id: str | None = None
    region_name: str | None = None
    risk_level: str | None = None
    chapter: str = ""
    page: int | None = None
    summary_excerpt: str = ""
    evidence_quality: str = ""


class RagIncidentListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    incidents: list[RagIncident] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


# --- §2.4 /health -------------------------------------------------------------


class AgentHealthResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = "unknown"
    search_index_reachable: bool | None = None
    llm_reachable: bool | None = None
    corpus_indexed: bool = False
    corpus_chunk_count: int = 0
    corpus_record_count: int = 0
    rerank_mode: str | None = None
    version: str | None = None


# The agent's own trace event (§1.2). The gateway persists these verbatim.
class TraceEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    step_type: str
    sequence_number: int = 0
    duration_ms: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)
