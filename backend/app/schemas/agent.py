"""Internal API shapes — the agent service (API_CONTRACT Part 2).

These are *our* mirror of Lakshitha's contract. Defined twice on purpose: a shared
package would cost packaging setup and a coordinated redeploy for a handful of
small classes. When the contract changes, both sides change.

Response models are deliberately lenient (`extra="allow"`, wide optionals) so an
extra field from the agent service never 500s the gateway.
"""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Confidence


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
    page_count: int | None = None
    error_message: str | None = None
    duration_ms: int | None = None


# --- §2.2 /rag/query ----------------------------------------------------------


class RagQueryRequest(BaseModel):
    question: str
    document_ids: list[UUID] | None = None
    top_k: int = 6
    conversation_history: list[ConversationTurn] = Field(default_factory=list)


class RagCitation(BaseModel):
    """No `document_name` — the agent service stays free of app-DB coupling."""

    model_config = ConfigDict(extra="allow")

    marker: int
    document_id: UUID
    chunk_id: str | None = None
    page: int | None = None
    section: str | None = None
    excerpt: str = ""
    relevance_score: float = 0.0


class RagQueryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    answer: str
    citations: list[RagCitation] = Field(default_factory=list)
    confidence: Confidence = "insufficient"
    has_sufficient_evidence: bool = False
    retrieved_chunk_count: int | None = None
    duration_ms: int | None = None


# --- §2.3 /agent/run ----------------------------------------------------------


class AgentRunCitation(BaseModel):
    marker: int
    document_id: UUID
    excerpt: str


class AgentRunRequest(BaseModel):
    question: str
    answer: str
    citations: list[AgentRunCitation] = Field(default_factory=list)


class AgentRunSuggestedAction(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["flag_invoice", "draft_email", "create_task"]
    title: str
    rationale: str
    payload: dict[str, Any] = Field(default_factory=dict)
    supporting_citations: list[int] = Field(default_factory=list)


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    suggested_action: AgentRunSuggestedAction | None = None
    duration_ms: int | None = None


# --- §2.4 /health -------------------------------------------------------------


class AgentHealthResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = "unknown"
    search_index_reachable: bool | None = None
    llm_reachable: bool | None = None
    version: str | None = None
