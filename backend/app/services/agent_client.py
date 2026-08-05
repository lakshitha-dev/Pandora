"""HTTP client for the agent service (API_CONTRACT Part 2).

The agent service is internal — no Supabase JWT, a shared `X-Internal-Key` header
instead. Timeouts are hard: 30 s on `/agent/sitrep` and `/rag/query`, 60 s on
`/rag/ingest`. A timeout returns 504 `agent_service_timeout` to the browser rather
than hanging it.

`AGENT_STUB_MODE=true` short-circuits every call with the contract's own example
payloads — the §1.1 report, the §1.4 refusal, and the §14.3 conflict — so the
frontend and the gateway can be integrated before the agent service is deployed.
"""

import asyncio
import base64
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core import errors
from app.core.config import Settings
from app.core.logging import get_logger
from app.schemas.agent import (
    AgentHealthResponse,
    RagIngestRequest,
    RagIngestResponse,
    RagQueryRequest,
    RagQueryResponse,
    SitrepRequest,
    SitrepResponse,
    TraceEvent,
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
        self, method: str, path: str, *, timeout_seconds: float, json: Any | None = None
    ) -> httpx.Response:
        if self._client is None:
            raise errors.agent_service_unavailable("The agent client is not initialised.")
        try:
            response = await self._client.request(
                method, path, json=json, timeout=timeout_seconds
            )
        except httpx.TimeoutException as exc:
            logger.warning("agent timeout %s %s after %ss", method, path, timeout_seconds)
            raise errors.agent_service_timeout(
                f"The agent service did not respond within {timeout_seconds:.0f}s."
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
            timeout_seconds=self._settings.agent_ingest_timeout_seconds,
            json=payload.model_dump(mode="json"),
        )
        return RagIngestResponse.model_validate(response.json())

    # --- §2.3 sitrep — what /api/v1/ask runs on ---

    async def sitrep(self, request: SitrepRequest) -> SitrepResponse:
        """The orchestrated path: classify, route, dispatch, validate, assemble."""
        if self._settings.agent_stub_mode:
            return _stub_sitrep(request)
        response = await self._request(
            "POST",
            "/agent/sitrep",
            timeout_seconds=self._settings.agent_query_timeout_seconds,
            json=request.model_dump(mode="json"),
        )
        return SitrepResponse.model_validate(response.json())

    # --- §2.3 sitrep, streamed — what /api/v1/ask/stream runs on ---

    async def stream_sitrep(self, request: SitrepRequest) -> AsyncIterator[TraceEvent]:
        """Yield §1.2 trace events as the orchestrator emits them.

        Nothing is accumulated: each frame is parsed and handed on the moment it
        arrives. Buffering here would defeat the entire point of the endpoint —
        three specialist orbs igniting at once is only visible if the events are
        live.
        """
        if self._settings.agent_stub_mode:
            async for event in _stub_stream(request, self._settings.stub_stream_delay_ms):
                yield event
            return

        if self._client is None:
            raise errors.agent_service_unavailable("The agent client is not initialised.")

        try:
            async with self._client.stream(
                "POST",
                "/agent/sitrep",
                json=request.model_dump(mode="json"),
                headers={"Accept": "text/event-stream"},
                # Applies between reads, not to the whole stream: a 30 s gap
                # means the orchestrator is gone, but a 25 s run is fine.
                timeout=httpx.Timeout(self._settings.agent_query_timeout_seconds),
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                    logger.warning(
                        "agent stream POST /agent/sitrep -> %s body=%s",
                        response.status_code,
                        response.text[:400],
                    )
                    raise errors.agent_service_unavailable(
                        f"The agent service returned {response.status_code}."
                    )
                async for event in _parse_sse(response.aiter_lines()):
                    yield event
        except httpx.TimeoutException as exc:
            logger.warning(
                "agent stream timed out after %ss", self._settings.agent_query_timeout_seconds
            )
            raise errors.agent_service_timeout(
                "The agent service stopped sending orchestration events."
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("agent stream failed: %s", exc)
            raise errors.agent_service_unavailable(
                "Lost the connection to the agent service."
            ) from exc

    # --- §2.2 query — single-section retrieval, no orchestrator ---

    async def query(self, request: RagQueryRequest) -> RagQueryResponse:
        """Layer 1/2 path. `/ask` uses `sitrep()`; this backs focused section fills."""
        if self._settings.agent_stub_mode:
            return _stub_query(request)
        response = await self._request(
            "POST",
            "/rag/query",
            timeout_seconds=self._settings.agent_query_timeout_seconds,
            json=request.model_dump(mode="json"),
        )
        return RagQueryResponse.model_validate(response.json())

    # --- vector cleanup on document delete ---

    async def delete_document_vectors(self, document_id: uuid.UUID) -> bool:
        """Remove a document's vectors from Azure AI Search.

        Deletion crosses two stores: orphaned vectors mean the guardian cites
        documents they deleted. The agent service owns AI Search, so the gateway
        asks it rather than holding search credentials of its own.

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
                status="ok",
                search_index_reachable=True,
                llm_reachable=True,
                corpus_indexed=True,
                corpus_chunk_count=221,
                corpus_record_count=130,
                rerank_mode="llm",
                version="stub",
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


# --- SSE wire parsing ---------------------------------------------------------


async def _parse_sse(lines: AsyncIterator[str]) -> AsyncIterator[TraceEvent]:
    """Turn an SSE line stream into trace events, one frame at a time.

    Only `data:` matters — the frame's `event:` name duplicates `step_type`
    inside it. Comment lines (`: ping`, sse-starlette's keep-alive) are skipped,
    and a frame whose JSON doesn't parse is logged and dropped rather than
    killing a stream that is otherwise fine.
    """
    data_lines: list[str] = []

    async for line in lines:
        if line.startswith(":"):
            continue
        if line == "":
            if data_lines:
                event = _parse_frame("\n".join(data_lines))
                if event is not None:
                    yield event
                data_lines = []
            continue
        field, _, value = line.partition(":")
        if field == "data":
            data_lines.append(value[1:] if value.startswith(" ") else value)

    # A stream that ends without its blank-line terminator still has a frame.
    if data_lines:
        event = _parse_frame("\n".join(data_lines))
        if event is not None:
            yield event


def _parse_frame(data: str) -> TraceEvent | None:
    try:
        return TraceEvent.model_validate(json.loads(data))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("unparseable trace frame dropped: %s — %s", exc, data[:200])
        return None


# --- Stub fixtures — the contract's own examples ------------------------------
#
# The corpus document id from API_CONTRACT §1.1. `conftest.py` and any local
# seed should use the same id so `document_name` joins in stub mode.

_STUB_CORPUS_DOCUMENT_ID = "1a2b3c4d-2222-4e5f-9a8b-7c6d5e4f3a2b"

# Questions that exercise the grounded path. Anything else gets the §1.4 refusal,
# so the frontend sees both branches without a code change.
_STUB_GROUNDED_KEYWORDS = (
    "water",
    "turquoise",
    "reef",
    "fish",
    "awa",
    "incident",
    "plume",
    "vent",
    "species",
)


def _stub_ingest(document_id: uuid.UUID) -> RagIngestResponse:
    return RagIngestResponse(
        document_id=document_id,
        status="indexed",
        chunk_count=23,
        record_count=0,
        page_count=9,
        chunking_mode="narrative",
        error_message=None,
        duration_ms=4210,
    )


def _stub_citations() -> list[dict[str, Any]]:
    return [
        {
            "marker": 1,
            "document_id": _STUB_CORPUS_DOCUMENT_ID,
            "chunk_id": "1a2b3c4d-chunk-0031",
            "record_id": "INC-001",
            "record_type": "incident",
            "title": "Turquoise Water Event",
            "chapter": "12 · Environmental Threats and Emergency Response",
            "section": "Plausible causes",
            "page": 40,
            "region_id": "REG-01",
            "excerpt": (
                "Plausible causes include mineral sediment, plankton bloom, chemical "
                "release, or light reflection. No single cause has been confirmed."
            ),
            "relevance_score": 0.94,
            "rerank_score": 9.4,
            "evidence_quality": "provisional_interpretation",
            "risk_level": "high",
            "record_date": None,
        },
        {
            "marker": 2,
            "document_id": _STUB_CORPUS_DOCUMENT_ID,
            "chunk_id": "1a2b3c4d-chunk-0164",
            "record_id": "LAB-C",
            "record_type": "field_note",
            "title": "Laboratory Note LAB-C",
            "chapter": "14 · Monitoring Data",
            "section": "14.3 Conflicting Field Notes",
            "page": 47,
            "region_id": "REG-01",
            "excerpt": (
                "Detected elevated harmless carbonate particles and moderate plankton "
                "density, but the sample chain-of-custody form was incomplete."
            ),
            "relevance_score": 0.88,
            "rerank_score": 8.8,
            "evidence_quality": "disputed_report",
            "risk_level": None,
            "record_date": "2026-06-05",
        },
    ]


def _stub_sitrep(request: SitrepRequest) -> SitrepResponse:
    """The §1.1 example, or the §1.4 refusal for anything off-corpus."""
    lowered = request.question.lower()
    if not any(word in lowered for word in _STUB_GROUNDED_KEYWORDS):
        return _stub_insufficient_sitrep()

    return SitrepResponse.model_validate(
        {
            "situation_report": {
                "priority_class": "W3",
                "priority_label": "EMERGENCY",
                "priority_reason": (
                    "Fish avoidance and water discolouration with offshore movement reported."
                ),
                "priority_citation": "§4.5 Water Incident Classification",
                "priority_page": 12,
                "affected_region_ids": ["REG-01"],
                "assembly_mode": "sitrep",
                "confidence_level": "medium",
                "confidence_reason": (
                    "Moderate — 3 sources, 1 unresolved conflict, chain of custody incomplete"
                ),
                "was_partial": False,
                "sections": [
                    {
                        "section_type": "affected_species",
                        "owning_agent": "marine_life_protector",
                        "status": "filled",
                        "empty_reason": None,
                        "content": (
                            "**FAU-001 Tideglass Grazer** — juveniles are documented as "
                            "vulnerable to turbidity in shallow shelf habitat [FAU-001 p.11]. "
                            "**FAU-002 Ribbonfin Skimmer** — recorded as sensitive to surface "
                            "oil films [FAU-002 p.11]."
                        ),
                        "claim_count": 2,
                        "supported_claim_count": 2,
                        "duration_ms": 2610,
                        "display_order": 2,
                    },
                    {
                        "section_type": "likely_causes",
                        "owning_agent": "incident_investigator",
                        "status": "filled",
                        "empty_reason": None,
                        "content": (
                            "**No cause is established.** Three records make incompatible "
                            "claims about this event and the corpus does not resolve them "
                            "[FN-A p.47] [FN-B p.47] [LAB-C p.47]. `INC-001` lists four "
                            "plausible causes without confirming any [INC-001 p.40]."
                        ),
                        "claim_count": 3,
                        "supported_claim_count": 3,
                        "duration_ms": 3180,
                        "display_order": 3,
                    },
                    {
                        "section_type": "recommended_actions",
                        "owning_agent": "emergency_responder",
                        "status": "filled",
                        "empty_reason": None,
                        "content": (
                            "1. Record observations and collect samples upstream and "
                            "downstream [INC-001 p.40].\n"
                            "2. Restrict sensitive water use pending results [§4.5 p.12].\n"
                            "3. Issue a public update naming the cause as **not yet "
                            "confirmed** [POL-010 p.46]."
                        ),
                        "claim_count": 3,
                        "supported_claim_count": 3,
                        "duration_ms": 2890,
                        "display_order": 4,
                    },
                ],
            },
            "citations": _stub_citations(),
            "grounding": {
                "groundedness": 96,
                "rules": [
                    {
                        "number": 1,
                        "name": "Cite record IDs for specific claims",
                        "passed": True,
                        "detail": "3/3 factual sentences carry a resolving marker",
                    },
                    {
                        "number": 2,
                        "name": "Multiple causes stay hypotheses",
                        "passed": True,
                        "detail": "INC-001's four causes presented unranked",
                    },
                ],
                "unsupported_sentences": [],
            },
            "conflicts": [
                {
                    "record_ids": ["FN-A", "FN-B", "LAB-C"],
                    "nature": (
                        "Three records propose incompatible causes for the same colour "
                        "change at Awa Reef."
                    ),
                    "reliability_limitation": "No record has confirmed sampling.",
                    "positions": [
                        {
                            "record_id": "FN-A",
                            "claim": (
                                "Plankton bloom; began after three calm hot days; "
                                "no chemical odor."
                            ),
                            "evidence_quality": "disputed_report",
                            "reliability_limitation": (
                                "Interpretation only; no chemical sampling performed."
                            ),
                        },
                        {
                            "record_id": "FN-B",
                            "claim": (
                                "Upstream pigment workshop maintenance; damaged waste "
                                "container observed."
                            ),
                            "evidence_quality": "disputed_report",
                            "reliability_limitation": (
                                "Entry of material into the water was never confirmed."
                            ),
                        },
                        {
                            "record_id": "LAB-C",
                            "claim": (
                                "Elevated harmless carbonate particles and moderate "
                                "plankton density."
                            ),
                            "evidence_quality": "disputed_report",
                            "reliability_limitation": (
                                "Sample chain-of-custody form incomplete."
                            ),
                        },
                    ],
                    "resolution_recommendation": (
                        "Documented resampling per checklist A.1 — Water Investigation."
                    ),
                }
            ],
            "has_sufficient_evidence": True,
            "insufficient_evidence": None,
            "llm_call_count": 6,
            "duration_ms": 5240,
            "top_rerank_score": 9.4,
        }
    )


def _stub_insufficient_sitrep() -> SitrepResponse:
    """§1.4 — the honest refusal, exactly as the agent service emits it: one text block."""
    return SitrepResponse.model_validate(
        {
            "situation_report": {
                "priority_class": "Informational",
                "priority_label": "OBSERVATION",
                "priority_reason": "No incident indicators detected in the available evidence.",
                "priority_citation": "",
                "priority_page": None,
                "affected_region_ids": [],
                "assembly_mode": "sitrep",
                "confidence_level": "insufficient",
                "confidence_reason": (
                    "Insufficient — no record scored above the relevance threshold"
                ),
                "was_partial": False,
                "sections": [
                    {
                        "section_type": "affected_species",
                        "owning_agent": "marine_life_protector",
                        "status": "empty",
                        "empty_reason": "No species records matched this query.",
                        "content": "",
                        "claim_count": 0,
                        "supported_claim_count": 0,
                        "duration_ms": 420,
                        "display_order": 2,
                    }
                ],
            },
            "citations": [],
            "grounding": {"groundedness": 0, "rules": [], "unsupported_sentences": []},
            "conflicts": [],
            "has_sufficient_evidence": False,
            "insufficient_evidence": (
                "The available Pandora knowledge base does not contain sufficient "
                "evidence to answer this question.\n\n"
                "Searched: the full Pandora knowledge base.\n"
                "Recommend field investigation and additional properly documented "
                "sampling to resolve this."
            ),
            "llm_call_count": 2,
            "duration_ms": 1840,
            "top_rerank_score": 2.1,
        }
    )


def _stub_trace_payloads(request: SitrepRequest) -> list[tuple[str, dict[str, Any]]]:
    """The §1.2 event list for the stub report, in the order it would really happen.

    Three specialists start together and finish out of order — that overlap is
    the whole point of the trace, so the fixture has to show it. The terminal
    `answer.completed` carries the §2.3 body itself, which is what §1.2 requires
    of a client that uses this endpoint alone.
    """
    result = _stub_sitrep(request)
    report = result.situation_report
    sufficient = result.has_sufficient_evidence

    steps: list[tuple[str, dict[str, Any]]] = [
        ("query.received", {"question": request.question}),
        (
            "query.rewritten",
            {"variants": [request.question, "water discolouration fish avoidance Awa Reef"]},
        ),
        (
            "query.classified",
            {
                "use_case": "emergency_response",
                "severity_class": report.priority_class,
                "query_shape": "incident_description",
            },
        ),
        (
            "priority.classified",
            {
                "class": report.priority_class,
                "label": report.priority_label,
                "reason": report.priority_reason,
                "citation": report.priority_citation or None,
                "page": report.priority_page,
            },
        ),
    ]
    if report.affected_region_ids:
        steps.append(
            (
                "map.zone_lit",
                {
                    "region_ids": report.affected_region_ids,
                    "priority_class": report.priority_class,
                },
            )
        )

    specialists = [s.owning_agent for s in report.sections]
    steps += [
        (
            "route.decided",
            {
                "mode": report.assembly_mode,
                "specialists": specialists,
                "reason": (
                    "Incident indicators detected → sitrep mode → "
                    f"dispatching {len(specialists)} specialists in parallel"
                ),
            },
        ),
        (
            "retrieval.started",
            {"agent": "orchestrator", "filters": {"record_type": ["incident"]}, "k": 30},
        ),
        (
            "retrieval.completed",
            {
                "candidate_count": 38,
                "kept_count": len(result.citations),
                "top_rerank_score": result.top_rerank_score,
            },
        ),
    ]

    # All three ignite, then fill — interleaved, not one after another.
    for section in report.sections:
        steps.append(
            (
                "section.filling",
                {"section_type": section.section_type, "owning_agent": section.owning_agent},
            )
        )
    for section in report.sections:
        steps.append(
            (
                "agent.thinking",
                {
                    "agent": section.owning_agent,
                    "source_count": len(result.citations),
                    "elapsed_ms": section.duration_ms // 2,
                },
            )
        )
    for section in report.sections:
        if section.status == "filled":
            steps.append(
                (
                    "section.completed",
                    {
                        "section_type": section.section_type,
                        "claim_count": section.claim_count,
                        "source_count": len(result.citations),
                        "duration_ms": section.duration_ms,
                    },
                )
            )
            steps.append(
                (
                    "agent.completed",
                    {
                        "agent": section.owning_agent,
                        "claim_count": section.claim_count,
                        "source_count": len(result.citations),
                        "duration_ms": section.duration_ms,
                    },
                )
            )
        else:
            steps.append(
                (
                    "section.unavailable",
                    {
                        "section_type": section.section_type,
                        "empty_reason": section.empty_reason,
                    },
                )
            )

    for conflict in result.conflicts:
        steps.append(
            (
                "conflict.detected",
                {"record_ids": conflict.record_ids, "conflict_nature": conflict.nature},
            )
        )

    steps += [
        ("validation.running", {"rule_count": 8}),
        (
            "validation.result",
            {
                "rules": [rule.model_dump(mode="json") for rule in result.grounding.rules],
                "groundedness": result.grounding.groundedness,
            },
        ),
        (
            "answer.completed",
            {
                **result.model_dump(mode="json"),
                "llm_call_count": result.llm_call_count,
                "latency_ms": result.duration_ms,
                "citation_count": len(result.citations),
                "has_sufficient_evidence": sufficient,
            },
        ),
    ]
    return steps


async def _stub_stream(request: SitrepRequest, delay_ms: int) -> AsyncIterator[TraceEvent]:
    """Replay the fixture trace. `STUB_STREAM_DELAY_MS` paces it for a demo."""
    elapsed = 0
    for sequence, (step_type, payload) in enumerate(_stub_trace_payloads(request), start=1):
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000)
        elapsed += delay_ms
        yield TraceEvent(
            step_type=step_type,
            sequence_number=sequence,
            duration_ms=elapsed,
            payload=payload,
        )


def _stub_query(request: RagQueryRequest) -> RagQueryResponse:
    """The §2.2 example — one section, no orchestrator."""
    section_type = request.section_type or "likely_causes"
    return RagQueryResponse.model_validate(
        {
            "sections": [
                {
                    "section_type": section_type,
                    "status": "filled",
                    "empty_reason": None,
                    "content": (
                        "**No cause is established.** [FN-A p.47] [FN-B p.47] [LAB-C p.47]"
                    ),
                    "claim_count": 3,
                    "supported_claim_count": 3,
                    "owning_agent": "incident_investigator",
                    "duration_ms": 3180,
                }
            ],
            "citations": _stub_citations(),
            "grounding": {"groundedness": 96, "rules": [], "unsupported_sentences": []},
            "conflicts": [],
            "has_sufficient_evidence": True,
            "retrieved_chunk_count": 6,
            "top_rerank_score": 9.4,
            "rerank_mode": "llm",
            "duration_ms": 3180,
        }
    )
