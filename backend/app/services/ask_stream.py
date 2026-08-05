"""`GET /api/v1/ask/stream` — the orchestration trace, agent → gateway → browser.

Wow feature 1 depends on this endpoint: three specialist orbs igniting at once
and three sections filling out of order is only *perceivable* if the events
arrive live. So the gateway forwards every frame the moment it arrives and
**never buffers** — the one rule §1.2 states in bold.

Two things the gateway does beyond forwarding:

  1. **The terminal event.** §1.2 requires `answer.completed` to carry the
     complete §1.1 body, so a client can use this endpoint alone. The agent's
     own terminal event carries counts, so the gateway replaces it with the
     assembled report — `document_name` joined, `answer_id` minted.
  2. **Persistence.** The report and the full trace are written to `answers`,
     which is what makes replay possible (§1.5, `SOLUTION.md` §9.3).

Failures mid-stream become a terminal `error` event, never a dropped connection:
the client is told what happened in the same channel it is already reading.
"""

import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import Answer
from app.db.session import get_session_factory
from app.schemas.agent import ConversationTurn, SitrepRequest, SitrepResponse, TraceEvent
from app.schemas.ask import AskRequest, AskResponse
from app.services import ask as ask_service
from app.services import documents as document_service
from app.services import report_mapping
from app.services.agent_client import AgentClient

logger = get_logger(__name__)

ANSWER_COMPLETED = "answer.completed"
ERROR = "error"


class StreamContext:
    """What the request-scoped session resolved before the stream opened.

    The guards run *before* the response starts so `401` and `422` are real HTTP
    statuses carrying the error envelope, not events an `EventSource` client
    would have to be taught to read. Everything after this point is an event.
    """

    def __init__(self, conversation_id: uuid.UUID, history: list[ConversationTurn]) -> None:
        self.conversation_id = conversation_id
        self.history = history


async def prepare(
    session: AsyncSession, user_id: uuid.UUID, request: AskRequest
) -> StreamContext:
    """Guard, then resolve the conversation. Raises `AppError` before streaming."""
    indexed = await document_service.count_indexed_documents(
        session, user_id, request.document_ids
    )
    if indexed == 0:
        raise errors.corpus_not_indexed()

    conversation = await ask_service.resolve_conversation(
        session, user_id, request.conversation_id, request.question
    )
    history = await ask_service.last_turn(session, conversation.id)
    return StreamContext(conversation_id=conversation.id, history=history)


async def stream(
    agent: AgentClient, user_id: uuid.UUID, request: AskRequest, context: StreamContext
) -> AsyncIterator[dict[str, str]]:
    """Yield sse-starlette frames: every agent event, then our `answer.completed`."""
    started = time.perf_counter()
    trace: list[dict[str, Any]] = []
    completed = False

    try:
        async for event in agent.stream_sitrep(
            SitrepRequest(
                question=request.question,
                conversation_id=str(context.conversation_id),
                document_ids=request.document_ids,
                mode=None,
                conversation_history=context.history,
            )
        ):
            trace.append(event.model_dump(mode="json"))

            if event.step_type == ERROR:
                # The orchestrator gave up. Pass its code through unchanged and stop.
                completed = True
                yield _frame(event)
                return

            if event.step_type != ANSWER_COMPLETED:
                yield _frame(event)
                continue

            completed = True
            body = await _assemble(agent, user_id, request, context, event, trace, started)
            yield {
                "event": ANSWER_COMPLETED,
                "data": TraceEvent(
                    step_type=ANSWER_COMPLETED,
                    sequence_number=event.sequence_number,
                    duration_ms=body.latency_ms,
                    payload=body.model_dump(mode="json", by_alias=True),
                ).model_dump_json(),
            }
            return

    except errors.AppError as exc:
        logger.warning("ask/stream failed mid-trace: %s", exc.code)
        yield _error_frame(len(trace) + 1, exc.code, exc.message)
        return
    except Exception as exc:  # noqa: BLE001 — a crash must still terminate the stream
        logger.exception("ask/stream crashed: %s", exc)
        yield _error_frame(len(trace) + 1, "internal_error", "Something went wrong on our side.")
        return

    if not completed:
        # The agent hung up without a terminal event. Say so rather than leaving
        # the browser spinning on a stream that will never produce a report.
        logger.warning("agent stream ended after %d events with no terminal event", len(trace))
        yield _error_frame(
            len(trace) + 1,
            "agent_service_unavailable",
            "The agent service ended the orchestration without a result.",
        )


async def _assemble(
    agent: AgentClient,
    user_id: uuid.UUID,
    request: AskRequest,
    context: StreamContext,
    event: TraceEvent,
    trace: list[dict[str, Any]],
    started: float,
) -> AskResponse:
    """Turn the agent's terminal event into the §1.1 body, and persist both."""
    result = _result_from_payload(event.payload)
    if result is None:
        # The agent's `answer.completed` carried counts only, so the report has
        # to be fetched. This costs a second orchestration — see the note in
        # docs/PROJECT.md; one extra field on the agent's payload removes it.
        logger.warning(
            "agent answer.completed carried no situation_report (§1.2 requires the "
            "full body) — re-running /agent/sitrep in JSON mode to assemble it"
        )
        result = await agent.sitrep(
            SitrepRequest(
                question=request.question,
                conversation_id=str(context.conversation_id),
                document_ids=request.document_ids,
                mode=None,
                conversation_history=context.history,
            )
        )

    latency_ms = int((time.perf_counter() - started) * 1000)

    # An explicit factory session, not the request's: a streaming response
    # outlives its request-scoped dependencies, and committing from inside an
    # `async for` over `session_scope()` would be skipped on the way out.
    async with get_session_factory()() as session:
        names = await ask_service.document_names(
            session, user_id, report_mapping.citation_document_ids(result.citations)
        )
        citations = report_mapping.to_citations(result.citations, names)
        situation_report = report_mapping.to_situation_report(result)
        insufficient = (
            report_mapping.to_insufficient_evidence(result, citations)
            if not result.has_sufficient_evidence
            else None
        )

        answer_row = Answer(
            id=uuid.uuid4(),
            conversation_id=context.conversation_id,
            user_id=user_id,
            question=request.question,
            role_lens=request.role_lens or "guardian",
            situation_report=situation_report.model_dump(mode="json", by_alias=True),
            citations=[c.model_dump(mode="json") for c in citations],
            insufficient_evidence=(
                insufficient.model_dump(mode="json") if insufficient is not None else None
            ),
            # The trace as the browser saw it. Replay is demo insurance: if the
            # live network stalls, we replay this at full speed (§1.5).
            agent_steps=trace,
            confidence=situation_report.confidence.level,
            groundedness=situation_report.confidence.groundedness,
            priority_class=situation_report.priority.class_,
            assembly_mode=situation_report.assembly_mode,
            affected_region_ids=situation_report.affected_region_ids,
            citation_count=len(citations),
            had_conflict=bool(situation_report.conflicts),
            was_partial=situation_report.was_partial,
            has_sufficient_evidence=result.has_sufficient_evidence,
            llm_call_count=result.llm_call_count,
            latency_ms=latency_ms,
            created_at=utcnow(),
        )
        session.add(answer_row)
        await session.commit()

        logger.info(
            "ask/stream answered id=%s steps=%d priority=%s sufficient=%s latency_ms=%d",
            answer_row.id,
            len(trace),
            situation_report.priority.class_,
            result.has_sufficient_evidence,
            latency_ms,
        )

        return AskResponse(
            answer_id=answer_row.id,
            conversation_id=context.conversation_id,
            situation_report=situation_report,
            insufficient_evidence=insufficient,
            citations=citations,
            has_sufficient_evidence=result.has_sufficient_evidence,
            llm_call_count=result.llm_call_count,
            latency_ms=latency_ms,
        )


def _result_from_payload(payload: dict[str, Any]) -> SitrepResponse | None:
    """The §2.3 body, if the terminal event carried one."""
    if "situation_report" not in payload:
        return None
    try:
        return SitrepResponse.model_validate(payload)
    except ValueError as exc:
        logger.warning("answer.completed payload did not validate as a §2.3 body: %s", exc)
        return None


def _frame(event: TraceEvent) -> dict[str, str]:
    return {"event": event.step_type, "data": event.model_dump_json()}


def _error_frame(sequence_number: int, code: str, message: str) -> dict[str, str]:
    return _frame(
        TraceEvent(
            step_type=ERROR,
            sequence_number=sequence_number,
            payload={"code": code, "message": message},
        )
    )
