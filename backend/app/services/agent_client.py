"""HTTP client for the agent service (API_CONTRACT Part 2).

The agent service is internal — no Supabase JWT, a shared `X-Internal-Key` header
instead. Timeouts are hard: 30 s on query, 60 s on ingest. A timeout returns
504 `agent_service_timeout` to the browser rather than hanging it.

`AGENT_STUB_MODE=true` short-circuits every call with the contract's own example
payloads, so the frontend and the gateway can be integrated before agent/ exists.
"""

import base64
import uuid
from typing import Any

import httpx

from app.core import errors
from app.core.config import Settings
from app.core.logging import get_logger
from app.schemas.agent import (
    AgentHealthResponse,
    AgentRunRequest,
    AgentRunResponse,
    RagIngestRequest,
    RagIngestResponse,
    RagQueryRequest,
    RagQueryResponse,
)

logger = get_logger(__name__)


class AgentClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._base_url = settings.agent_service_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    # --- lifecycle ---

    async def start(self) -> None:
        if self._settings.agent_stub_mode:
            return
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"X-Internal-Key": self._settings.agent_service_key},
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # --- plumbing ---

    async def _request(
        self, method: str, path: str, *, timeout: float, json: Any | None = None
    ) -> httpx.Response:
        if self._client is None:
            raise errors.agent_service_unavailable("The agent client is not initialised.")
        try:
            response = await self._client.request(method, path, json=json, timeout=timeout)
        except httpx.TimeoutException as exc:
            logger.warning("agent timeout %s %s after %ss", method, path, timeout)
            raise errors.agent_service_timeout(
                f"The agent service did not respond within {timeout:.0f}s."
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("agent unreachable %s %s: %s", method, path, exc)
            raise errors.agent_service_unavailable(
                "Could not reach the agent service."
            ) from exc

        if response.status_code >= 500:
            logger.warning("agent %s %s -> %s", method, path, response.status_code)
            raise errors.agent_service_unavailable(
                f"The agent service returned {response.status_code}."
            )
        if response.status_code >= 400:
            logger.warning(
                "agent %s %s -> %s body=%s", method, path, response.status_code, response.text[:400]
            )
            raise errors.agent_service_unavailable(
                f"The agent service rejected the request ({response.status_code})."
            )
        return response

    # --- §2.1 ingest ---

    async def ingest(
        self, *, document_id: uuid.UUID, file_name: str, content_type: str, content: bytes
    ) -> RagIngestResponse:
        payload = RagIngestRequest(
            document_id=document_id,
            file_name=file_name,
            content_type=content_type,
            content_base64=base64.b64encode(content).decode("ascii"),
        )
        if self._settings.agent_stub_mode:
            return _stub_ingest(document_id)
        response = await self._request(
            "POST",
            "/rag/ingest",
            timeout=self._settings.agent_ingest_timeout_seconds,
            json=payload.model_dump(mode="json"),
        )
        return RagIngestResponse.model_validate(response.json())

    # --- §2.2 query ---

    async def query(self, request: RagQueryRequest) -> RagQueryResponse:
        if self._settings.agent_stub_mode:
            return _stub_query(request)
        response = await self._request(
            "POST",
            "/rag/query",
            timeout=self._settings.agent_query_timeout_seconds,
            json=request.model_dump(mode="json"),
        )
        return RagQueryResponse.model_validate(response.json())

    # --- §2.3 agent run ---

    async def run_agent(self, request: AgentRunRequest) -> AgentRunResponse:
        if self._settings.agent_stub_mode:
            return _stub_agent_run(request)
        response = await self._request(
            "POST",
            "/agent/run",
            timeout=self._settings.agent_query_timeout_seconds,
            json=request.model_dump(mode="json"),
        )
        return AgentRunResponse.model_validate(response.json())

    # --- vector cleanup on document delete ---

    async def delete_document_vectors(self, document_id: uuid.UUID) -> bool:
        """Remove a document's vectors from Azure AI Search.

        Deletion crosses two stores: orphaned vectors mean the assistant cites
        documents the user deleted. The agent service owns AI Search, so the
        gateway asks it rather than holding search credentials of its own.

        NOTE: `DELETE /rag/documents/{id}` is a *proposed* addition to
        API_CONTRACT Part 2 — it is not in the frozen contract yet (see
        backend/README.md § Open contract question). Until Lakshitha ships it we
        treat a 404/405 as "endpoint not implemented", log it, and let the
        Postgres delete succeed rather than blocking the user on it.
        """
        if self._settings.agent_stub_mode:
            return True
        if self._client is None:
            return False
        try:
            response = await self._client.request(
                "DELETE", f"/rag/documents/{document_id}", timeout=15.0
            )
        except httpx.HTTPError as exc:
            logger.warning("vector cleanup failed for %s: %s", document_id, exc)
            return False
        if response.status_code in (404, 405, 501):
            logger.warning(
                "agent service has no DELETE /rag/documents endpoint (%s) — "
                "vectors for %s may be orphaned",
                response.status_code,
                document_id,
            )
            return False
        if response.status_code >= 400:
            logger.warning(
                "vector cleanup for %s returned %s", document_id, response.status_code
            )
            return False
        return True

    # --- §2.4 health ---

    async def health(self) -> AgentHealthResponse:
        if self._settings.agent_stub_mode:
            return AgentHealthResponse(
                status="ok", search_index_reachable=True, llm_reachable=True, version="stub"
            )
        if self._client is None:
            return AgentHealthResponse(status="unavailable")
        try:
            response = await self._client.get(
                "/health", timeout=self._settings.agent_health_timeout_seconds
            )
            if response.status_code != 200:
                return AgentHealthResponse(status="unhealthy")
            return AgentHealthResponse.model_validate(response.json())
        except httpx.HTTPError:
            return AgentHealthResponse(status="unavailable")


# --- Stub fixtures — the contract's own examples, verbatim -------------------

_STUB_DOC_ID = uuid.UUID("1a2b3c4d-2222-4e5f-9a8b-7c6d5e4f3a2b")
_STUB_AGREEMENT_ID = uuid.UUID("5e6f7a8b-3333-4b9c-8d1e-2f3a4b5c6d7e")


def _stub_ingest(document_id: uuid.UUID) -> RagIngestResponse:
    return RagIngestResponse(
        document_id=document_id,
        status="indexed",
        chunk_count=23,
        page_count=None,
        error_message=None,
        duration_ms=4210,
    )


def _stub_agent_run(request: AgentRunRequest) -> AgentRunResponse:
    """`suggested_action: null` is the common path — only the §1.1 example question
    produces an action, so the frontend sees both branches without a code change."""
    if "overdue" not in request.question.lower() or not request.citations:
        return AgentRunResponse(suggested_action=None, duration_ms=640)
    return AgentRunResponse.model_validate(
        {
            "suggested_action": {
                "type": "flag_invoice",
                "title": "Flag invoice #4471 as overdue",
                "rationale": (
                    "32 days overdue and past the 30-day threshold where the 2% late fee applies."
                ),
                "payload": {
                    "invoice_number": "INV-4471",
                    "supplier": "Silverline Supplies",
                    "amount": 120000.00,
                    "currency": "LKR",
                    "due_date": "2026-07-04",
                    "days_overdue": 32,
                },
                "supporting_citations": [1, 3],
            },
            "duration_ms": 980,
        }
    )


def _stub_query(request: RagQueryRequest) -> RagQueryResponse:
    """The §2.2 example. Returns the insufficient-evidence shape for questions
    that clearly aren't about the fixture, so the frontend can exercise both."""
    lowered = request.question.lower()
    if not any(word in lowered for word in ("invoice", "overdue", "supplier", "payment")):
        return RagQueryResponse(
            answer=(
                "I couldn't find enough evidence in your documents to answer this. "
                "I searched the indexed documents but found nothing relevant to this question."
            ),
            citations=[],
            confidence="insufficient",
            has_sufficient_evidence=False,
            retrieved_chunk_count=0,
            duration_ms=1840,
        )
    return RagQueryResponse.model_validate(
        {
            "answer": (
                "Two invoices are currently overdue. Invoice #4471 from Silverline Supplies "
                "for LKR 120,000 was due on 2026-07-04 and is 32 days overdue [1]. "
                "Invoice #4488 from Nimal Traders for LKR 45,500 was due on 2026-07-21 and is "
                "15 days overdue [2]. Silverline's terms specify a 2% late fee after 30 days [3]."
            ),
            "citations": [
                {
                    "marker": 1,
                    "document_id": str(_STUB_DOC_ID),
                    "chunk_id": "1a2b3c4d-chunk-0031",
                    "page": 3,
                    "section": "Outstanding",
                    "excerpt": (
                        "INV-4471 | Silverline Supplies | LKR 120,000.00 | "
                        "Due: 2026-07-04 | Status: UNPAID"
                    ),
                    "relevance_score": 0.94,
                },
                {
                    "marker": 2,
                    "document_id": str(_STUB_DOC_ID),
                    "chunk_id": "1a2b3c4d-chunk-0032",
                    "page": 3,
                    "section": "Outstanding",
                    "excerpt": (
                        "INV-4488 | Nimal Traders | LKR 45,500.00 | "
                        "Due: 2026-07-21 | Status: UNPAID"
                    ),
                    "relevance_score": 0.91,
                },
                {
                    "marker": 3,
                    "document_id": str(_STUB_AGREEMENT_ID),
                    "chunk_id": "5e6f7a8b-chunk-0007",
                    "page": 7,
                    "section": "6. Payment Terms",
                    "excerpt": (
                        "A late payment charge of 2% per month applies to balances "
                        "outstanding beyond thirty (30) days."
                    ),
                    "relevance_score": 0.87,
                },
            ],
            "confidence": "high",
            "has_sufficient_evidence": True,
            "retrieved_chunk_count": 6,
            "duration_ms": 2870,
        }
    )
