"""HTTP client for the agent service (API_CONTRACT Part 2).

The agent service is internal — no Supabase JWT, a shared `X-Internal-Key` header
instead. Timeouts are hard: a timeout returns 504 `agent_service_timeout` to the
browser rather than hanging it.

The sitrep timeout is much larger than the query one on purpose. The agent's own
orchestration budget is measured in minutes, so a 30 s ceiling here would cut off
every orchestrated report just before it finished.

`AGENT_STUB_MODE=true` short-circuits every call with the contract's own example
payloads, so the frontend and the gateway can be integrated without the agent.
"""

import base64
import uuid
from collections.abc import AsyncIterator
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.core import errors
from app.core.config import Settings
from app.core.logging import get_logger
from app.schemas.agent import (
    AgentHealthResponse,
    RagIncidentListResponse,
    RagIngestRequest,
    RagIngestResponse,
    RagQueryRequest,
    RagQueryResponse,
    SitrepRequest,
    SitrepResponse,
)
from app.services import stub_fixtures

logger = get_logger(__name__)

_ModelT = TypeVar("_ModelT", bound=BaseModel)


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
        self,
        method: str,
        path: str,
        *,
        timeout_seconds: float,
        json: Any | None = None,
        params: Any | None = None,
    ) -> httpx.Response:
        if self._client is None:
            raise errors.agent_service_unavailable("The agent client is not initialised.")
        try:
            response = await self._client.request(
                method, path, json=json, params=params, timeout=timeout_seconds
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

    @staticmethod
    def _parse(model: type[_ModelT], response: httpx.Response, path: str) -> _ModelT:
        """Validate an agent payload, turning shape drift into a 502.

        Without this the two services falling out of sync surfaces as an opaque
        500 `internal_error` from the catch-all handler, which points at the
        gateway rather than at the contract mismatch that actually caused it.
        """
        try:
            return model.model_validate(response.json())
        except (ValidationError, ValueError) as exc:
            logger.error("agent %s returned an unexpected shape: %s", path, exc)
            raise errors.agent_service_unavailable(
                f"The agent service returned an unexpected response shape for {path}."
            ) from exc

    # --- §2.1 ingest ---

    async def ingest(
        self, *, document_id: uuid.UUID, file_name: str, content_type: str, content: bytes
    ) -> RagIngestResponse:
        payload = RagIngestRequest(
            document_id=str(document_id),
            file_name=file_name,
            content_type=content_type,
            content_base64=base64.b64encode(content).decode("ascii"),
        )
        if self._settings.agent_stub_mode:
            return stub_fixtures.ingest(document_id)
        response = await self._request(
            "POST",
            "/rag/ingest",
            timeout_seconds=self._settings.agent_ingest_timeout_seconds,
            json=payload.model_dump(mode="json"),
        )
        return self._parse(RagIngestResponse, response, "/rag/ingest")

    # --- §2.2 query ---

    async def query(self, request: RagQueryRequest) -> RagQueryResponse:
        if self._settings.agent_stub_mode:
            return stub_fixtures.query(request)
        response = await self._request(
            "POST",
            "/rag/query",
            timeout_seconds=self._settings.agent_query_timeout_seconds,
            json=request.model_dump(mode="json"),
        )
        return self._parse(RagQueryResponse, response, "/rag/query")

    # --- §2.3 sitrep ---

    async def sitrep(self, request: SitrepRequest) -> SitrepResponse:
        """The orchestrated path — classify, route, dispatch specialists, validate."""
        if self._settings.agent_stub_mode:
            return stub_fixtures.sitrep(request)
        response = await self._request(
            "POST",
            "/agent/sitrep",
            timeout_seconds=self._settings.agent_sitrep_timeout_seconds,
            json=request.model_dump(mode="json"),
        )
        return self._parse(SitrepResponse, response, "/agent/sitrep")

    async def stream_sitrep(self, request: SitrepRequest) -> AsyncIterator[tuple[str, str]]:
        """Yield `(event_name, data)` pairs as the agent produces them.

        Nothing is accumulated: the contract states the gateway MUST NOT buffer,
        because a trace that arrives all at once at the end is exactly the thing
        the endpoint exists to avoid showing.

        Errors are yielded as a terminal `error` frame rather than raised — the
        response has already begun, so there is no status code left to change,
        and dropping the connection would leave the rail frozen mid-run.
        """
        if self._settings.agent_stub_mode:
            for frame in stub_fixtures.sitrep_stream(request):
                yield frame
            return

        if self._client is None:
            yield ("error", stub_fixtures.error_frame(
                "agent_service_unavailable", "The agent client is not initialised."
            ))
            return

        event = "message"
        data_lines: list[str] = []
        try:
            async with self._client.stream(
                "POST",
                "/agent/sitrep",
                json=request.model_dump(mode="json"),
                headers={"Accept": "text/event-stream"},
                timeout=httpx.Timeout(
                    self._settings.agent_sitrep_timeout_seconds, connect=10.0
                ),
            ) as response:
                if response.status_code >= 400:
                    await response.aread()
                    logger.warning("agent sitrep stream -> %s", response.status_code)
                    yield ("error", stub_fixtures.error_frame(
                        "agent_service_unavailable",
                        f"The agent service returned {response.status_code}.",
                    ))
                    return

                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[5:].strip())
                    elif not line:
                        # Blank line terminates a frame.
                        if data_lines:
                            yield (event, "\n".join(data_lines))
                        event, data_lines = "message", []
        except httpx.TimeoutException:
            logger.warning("agent sitrep stream timed out")
            yield ("error", stub_fixtures.error_frame(
                "agent_service_timeout", "The agent service did not respond in time."
            ))
        except httpx.HTTPError as exc:
            logger.warning("agent sitrep stream failed: %s", exc)
            yield ("error", stub_fixtures.error_frame(
                "agent_service_unavailable", "Lost the connection to the agent service."
            ))

    # --- §1.6 incidents ---

    async def incidents(
        self,
        *,
        risk_level: str | None = None,
        region_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> RagIncidentListResponse:
        if self._settings.agent_stub_mode:
            return stub_fixtures.incidents(limit=limit, offset=offset)
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if risk_level:
            params["risk_level"] = risk_level
        if region_id:
            params["region_id"] = region_id
        response = await self._request(
            "GET",
            "/rag/incidents",
            timeout_seconds=self._settings.agent_query_timeout_seconds,
            params=params,
        )
        return self._parse(RagIncidentListResponse, response, "/rag/incidents")

    # --- vector cleanup on document delete ---

    async def delete_document_vectors(self, document_id: uuid.UUID) -> bool:
        """Remove a document's vectors from Azure AI Search.

        Deletion crosses two stores: orphaned vectors mean the assistant cites
        documents the user deleted. The agent service owns AI Search, so the
        gateway asks it rather than holding search credentials of its own.
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
                corpus_chunk_count=195,
                corpus_record_count=149,
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
        except (httpx.HTTPError, ValidationError, ValueError):
            return AgentHealthResponse(status="unavailable")
