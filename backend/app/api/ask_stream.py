"""`GET /api/v1/ask/stream` — the orchestration trace (API_CONTRACT §1.2).

The trace is what makes the agentic architecture *perceivable*: three orbs
igniting at once, three sections filling out of order. That only works if the
events reach the browser as they happen, so **this endpoint must not buffer**.
Frames are forwarded one at a time, straight from the agent.

Persistence is a side effect of the pass-through, not a second pass: trace
events are collected as they fly by and written once at the end, together with
the answer row built from the terminal `answer.completed` payload. A client that
uses only this endpoint still ends up with a durable report for §1.5.
"""

import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import ValidationError
from sse_starlette.sse import EventSourceResponse

from app.core.dependencies import AgentDep, DbSession, StreamUserDep
from app.core.logging import get_logger
from app.db.session import session_scope
from app.schemas import agent as ag
from app.schemas.common import RoleLens
from app.services import ask as ask_service
from app.services import mapping

logger = get_logger(__name__)
router = APIRouter(tags=["ask"])

_TERMINAL = {"answer.completed", "error"}


@router.get(
    "/ask/stream",
    summary="Stream the orchestration trace as the report is assembled",
    response_class=EventSourceResponse,
)
async def ask_stream(
    request: Request,
    session: DbSession,
    agent: AgentDep,
    user: StreamUserDep,
    question: str = Query(min_length=1, max_length=2000),
    conversation_id: uuid.UUID | None = None,
    document_ids: list[uuid.UUID] | None = Query(default=None),
    role_lens: RoleLens | None = None,
    # Consumed by the auth dependency; declared so it appears in the schema.
    access_token: str | None = None,
) -> EventSourceResponse:
    started = time.perf_counter()

    # The guard runs before the stream opens so a cold index is still a proper
    # 422 with the standard envelope, not an error frame the UI has to special-case.
    await ask_service.ensure_corpus_indexed(agent)

    conversation = await ask_service.resolve_conversation(
        session, user.id, conversation_id, question
    )
    conversation_uuid = conversation.id
    history = await ask_service.last_turn(session, conversation_uuid)
    await session.commit()

    sitrep_request = ag.SitrepRequest(
        question=question,
        conversation_id=str(conversation_uuid),
        document_ids=[str(d) for d in document_ids] if document_ids else None,
        conversation_history=history,
    )

    async def publish() -> AsyncIterator[dict[str, str]]:
        collected: list[ag.TraceEvent] = []
        final: dict[str, Any] | None = None

        async for event_name, data in agent.stream_sitrep(sitrep_request):
            # Client went away — stop pulling from the agent rather than
            # finishing a report nobody is reading.
            if await request.is_disconnected():
                logger.info("client disconnected from trace stream")
                return

            try:
                parsed = json.loads(data)
            except json.JSONDecodeError:
                logger.warning("dropping unparseable trace frame: %s", data[:200])
                continue

            step_type = parsed.get("step_type", event_name)
            if step_type == "answer.completed":
                final = parsed.get("payload")
            else:
                try:
                    collected.append(ag.TraceEvent.model_validate(parsed))
                except ValidationError:
                    # An unknown or malformed step must not break the stream —
                    # the contract says clients ignore unknown types silently,
                    # and the gateway holds itself to the same rule.
                    logger.debug("unrecognised trace frame %s", step_type)

            # Forward first, persist later. Yielding immediately is the point.
            yield {"event": step_type, "data": data}

            if step_type in _TERMINAL:
                break

        if final is None:
            return

        # A fresh session: the request-scoped one is not guaranteed to still be
        # open once the response body has started streaming.
        try:
            async for write_session in session_scope():
                await _persist(
                    write_session,
                    user_id=user.id,
                    conversation_id=conversation_uuid,
                    question=question,
                    final=final,
                    collected=collected,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
        except Exception:  # noqa: BLE001 - the user already has their report
            logger.exception("failed to persist streamed report")

    return EventSourceResponse(publish())


async def _persist(
    session,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    question: str,
    final: dict[str, Any],
    collected: list[ag.TraceEvent],
    latency_ms: int,
) -> None:
    result = ag.SitrepResponse.model_validate(final)
    report = mapping.map_situation_report(result)
    insufficient = mapping.map_insufficient_evidence(result)
    citations = await ask_service.join_document_names(session, user_id, result.citations)

    row = await ask_service.persist_answer(
        session,
        user_id=user_id,
        conversation_id=conversation_id,
        question=question,
        report=report,
        citations=citations,
        insufficient=insufficient,
        has_sufficient_evidence=result.has_sufficient_evidence,
        llm_call_count=result.llm_call_count,
        latency_ms=latency_ms,
    )
    await ask_service.persist_trace(session, row.id, collected)
    # session_scope commits on exit.
