"""Internal API shapes — the agent service (API_CONTRACT Part 2).

These are *our* mirror of Lakshitha's contract. Defined twice on purpose: a shared
package would cost packaging setup and a coordinated redeploy for a handful of
small classes. When the contract changes, both sides change.

Response models are deliberately lenient (`extra="allow"`, wide optionals, string
enums) so an extra or unrecognised field from the agent service never 500s the
gateway. Narrowing to the contract's enums happens in `services/report_mapping.py`,
where an unknown value degrades to a documented default instead of an exception.

**The agent service is flatter than the public contract.** `SitrepSituationReport`
carries `priority_class` / `priority_reason` / … as top-level strings and puts
groundedness under `grounding`; §1.1 nests them as `priority` and `confidence`
objects. That reshaping is the gateway's job — see `services/report_mapping.py`.
"""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


# --- §2.1 /rag/ingest ---------------------------------------------------------


class RagIngestRequest(BaseModel):
    document_id: UUID
    file_name: str
    content_type: str
    content_base64: str


class RagIngestResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    document_id: UUID
    status: Literal["indexed", "failed"]
    chunk_count: int | None = None
    # Corpus-style records detected by the `^(REG|STL|FAU|…)-\d+` boundary pattern.
    # 0 means it fell back to narrative chunking — normal for an uploaded document.
    record_count: int = 0
    page_count: int | None = None
    chunking_mode: str = "narrative"
    error_message: str | None = None
    duration_ms: int | None = None


# --- Shared response pieces ---------------------------------------------------


class AgentCitation(BaseModel):
    """No `document_name` — the agent service stays free of app-DB coupling.

    `document_id` is a plain string here: an unparseable id must not blow up the
    response, so the mapper substitutes a placeholder and logs instead.
    """

    model_config = ConfigDict(extra="allow")

    marker: int = 0
    document_id: str = ""
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
    # Not emitted by the agent service today; accepted so it flows through the
    # moment it is. §1.1 defaults it to an empty list.
    section_types: list[str] = Field(default_factory=list)


class GroundingRuleResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    number: int = 0
    name: str = ""
    passed: bool = False
    detail: str = ""


class Grounding(BaseModel):
    """All 8 of the corpus's §15.2 rules, each with pass/fail and a detail."""

    model_config = ConfigDict(extra="allow")

    groundedness: int = 0
    rules: list[GroundingRuleResult] = Field(default_factory=list)
    unsupported_sentences: list[str] = Field(default_factory=list)


class AgentConflictPosition(BaseModel):
    model_config = ConfigDict(extra="allow")

    record_id: str = ""
    claim: str = ""
    evidence_quality: str = ""
    reliability_limitation: str = ""


class AgentConflict(BaseModel):
    """`nature` is what the service sends; `conflict_nature` is the §1.1 name.

    Both are accepted so this keeps working whichever side lands the rename.
    """

    model_config = ConfigDict(extra="allow")

    record_ids: list[str] = Field(default_factory=list)
    nature: str = ""
    conflict_nature: str = ""
    reliability_limitation: str = ""
    positions: list[AgentConflictPosition] = Field(default_factory=list)
    resolution_recommendation: str = ""


class AgentReportSection(BaseModel):
    model_config = ConfigDict(extra="allow")

    section_type: str
    status: str = "filled"
    empty_reason: str | None = None
    content: str = ""
    claim_count: int = 0
    supported_claim_count: int = 0
    owning_agent: str = "orchestrator"
    duration_ms: int = 0
    display_order: int = 0


# --- §2.2 /rag/query ----------------------------------------------------------


class RagQueryRequest(BaseModel):
    """One section, or a whole report when `section_type` is null.

    Layers 1–2 and degradation rung 3 use this path directly, with no orchestrator.
    """

    question: str
    document_ids: list[UUID] | None = None
    top_k: int | None = 6
    record_type_filter: list[str] | None = None
    region_id_filter: list[str] | None = None
    section_type: str | None = None
    conversation_history: list[ConversationTurn] = Field(default_factory=list)


class RagQueryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    sections: list[AgentReportSection] = Field(default_factory=list)
    citations: list[AgentCitation] = Field(default_factory=list)
    grounding: Grounding = Field(default_factory=Grounding)
    conflicts: list[AgentConflict] = Field(default_factory=list)
    has_sufficient_evidence: bool = True
    retrieved_chunk_count: int = 0
    # 0.0–10.0. Below 4.5 the agent flips `has_sufficient_evidence` to false.
    top_rerank_score: float = 0.0
    rerank_mode: str = "none"
    duration_ms: int = 0


# --- §2.3 /agent/sitrep -------------------------------------------------------


class SitrepRequest(BaseModel):
    question: str
    conversation_id: str | None = None
    document_ids: list[UUID] | None = None
    # null lets the orchestrator decide — the normal case.
    mode: Literal["sitrep", "focused", "compare"] | None = None
    conversation_history: list[ConversationTurn] = Field(default_factory=list)


class SitrepSituationReport(BaseModel):
    model_config = ConfigDict(extra="allow")

    priority_class: str = "informational"
    priority_label: str = ""
    priority_reason: str = ""
    priority_citation: str = ""
    priority_page: int | None = None
    affected_region_ids: list[str] = Field(default_factory=list)
    assembly_mode: str = "sitrep"
    confidence_level: str = ""
    confidence_reason: str = ""
    was_partial: bool = False
    sections: list[AgentReportSection] = Field(default_factory=list)


class SitrepResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    situation_report: SitrepSituationReport
    citations: list[AgentCitation] = Field(default_factory=list)
    grounding: Grounding = Field(default_factory=Grounding)
    conflicts: list[AgentConflict] = Field(default_factory=list)
    has_sufficient_evidence: bool = True
    # A pre-rendered text block, not the §1.4 object. The gateway builds the
    # structured object; see `report_mapping.to_insufficient_evidence`.
    insufficient_evidence: str | None = None
    llm_call_count: int = 0
    duration_ms: int = 0
    top_rerank_score: float = 0.0


# --- §1.2 orchestration trace (streamed over SSE) -----------------------------


class TraceEvent(BaseModel):
    """One orchestration step, as the agent service frames it.

    `step_type` is intentionally an open string: §1.2's schema is **additive
    only**, and an unknown step type must flow through to the browser untouched
    rather than be dropped by a gateway that hasn't been redeployed yet.
    """

    model_config = ConfigDict(extra="allow")

    step_type: str
    sequence_number: int = 0
    duration_ms: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)


# --- §2.4 /health -------------------------------------------------------------


class AgentHealthResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = "unavailable"
    search_index_reachable: bool = False
    llm_reachable: bool = False
    # The single most important field: false means no query can work.
    corpus_indexed: bool = False
    corpus_chunk_count: int = 0
    corpus_record_count: int = 0
    rerank_mode: str = "none"
    version: str | None = None
