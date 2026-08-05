"""`/api/v1/ask` orchestration: guard → /agent/sitrep → map → join names → persist.

The gateway owns everything the agent service deliberately doesn't: who the user
is, whether the corpus is indexed, what the documents are called, and the audit
trail. The agent owns retrieval and reasoning, and the orchestrator already does
its own retrieval — so this is a single call, not query-then-run.
"""

import time
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import AgentStep, Answer, Conversation, Document
from app.schemas import agent as ag
from app.schemas.ask import AskRequest, AskResponse, SituationReport
from app.schemas.common import Citation
from app.services import mapping
from app.services.agent_client import AgentClient

logger = get_logger(__name__)

UNKNOWN_DOCUMENT_NAME = "(document unavailable)"


async def resolve_conversation(
    session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID | None, question: str
) -> Conversation:
    if conversation_id is not None:
        stmt = select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return existing
        # An unknown conversation_id starts a fresh conversation under the id the
        # client already holds, rather than 404ing mid-typing.
        logger.info("unknown conversation %s for user %s — creating it", conversation_id, user_id)

    conversation = Conversation(
        id=conversation_id or uuid.uuid4(),
        user_id=user_id,
        title=question[:200],
        created_at=utcnow(),
    )
    session.add(conversation)
    await session.flush()
    return conversation


async def last_turn(
    session: AsyncSession, conversation_id: uuid.UUID
) -> list[ag.ConversationTurn]:
    """Last turn only, for coreference. No long history — see PROJECT.md scope."""
    stmt = (
        select(Answer)
        .where(Answer.conversation_id == conversation_id)
        .order_by(Answer.created_at.desc())
        .limit(1)
    )
    previous = (await session.execute(stmt)).scalar_one_or_none()
    if previous is None:
        return []
    return [
        ag.ConversationTurn(role="user", content=previous.question),
        ag.ConversationTurn(role="assistant", content=previous.answer),
    ]


async def join_document_names(
    session: AsyncSession, user_id: uuid.UUID, citations: list[ag.RagCitation]
) -> list[Citation]:
    """The agent service returns `document_id` only; the name lives in Postgres.

    The preloaded corpus is matched on `is_preloaded` rather than ownership — it
    belongs to no user and every guardian cites it.
    """
    resolved: list[tuple[ag.RagCitation, uuid.UUID | None]] = [
        (c, mapping.resolve_document_id(c.document_id)) for c in citations
    ]
    wanted = {doc_id for _, doc_id in resolved if doc_id is not None}

    names: dict[uuid.UUID, str] = {}
    if wanted:
        stmt = select(Document.id, Document.file_name).where(
            Document.id.in_(wanted),
            or_(Document.user_id == user_id, Document.is_preloaded.is_(True)),
        )
        names = {row.id: row.file_name for row in (await session.execute(stmt)).all()}

    out: list[Citation] = []
    for citation, document_id in resolved:
        name = names.get(document_id) if document_id is not None else None
        if name is None:
            # Keep the citation: dropping it would break the [RECORD-ID] markers
            # already written into the report text.
            logger.warning("citation references unknown document %s", citation.document_id)
            name = UNKNOWN_DOCUMENT_NAME
        out.append(
            mapping.map_citation(
                citation, document_id or uuid.UUID(int=0), name
            )
        )
    return out


async def ensure_corpus_indexed(agent: AgentClient) -> None:
    """Guard before any LLM call — no wasted tokens, and a clear message for the UI.

    This asks the agent whether the *index* is seeded rather than counting the
    caller's Postgres rows. The preloaded corpus is the whole point of the
    product and belongs to no user, so an ownership count would refuse every
    question from a fresh account against a perfectly healthy index.
    """
    health = await agent.health()
    if health.status in ("unavailable", "unhealthy"):
        raise errors.agent_service_unavailable(
            "The agent service is not answering health checks."
        )
    if not health.corpus_indexed:
        raise errors.corpus_not_indexed()


async def persist_answer(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    question: str,
    report: SituationReport,
    citations: list[Citation],
    insufficient,  # InsufficientEvidence | None
    has_sufficient_evidence: bool,
    llm_call_count: int,
    latency_ms: int,
    answer_id: uuid.UUID | None = None,
) -> Answer:
    """Write one answer row. Shared by /ask and the SSE endpoint."""
    row = Answer(
        id=answer_id or uuid.uuid4(),
        conversation_id=conversation_id,
        user_id=user_id,
        question=question,
        answer=mapping.flatten_for_history(report),
        citations=[c.model_dump(mode="json") for c in citations],
        situation_report=report.model_dump(mode="json", by_alias=True),
        insufficient_evidence=(
            insufficient.model_dump(mode="json") if insufficient is not None else None
        ),
        priority_class=report.priority.class_,
        assembly_mode=report.assembly_mode,
        confidence=report.confidence.level,
        affected_region_ids=list(report.affected_region_ids),
        had_conflict=bool(report.conflicts),
        was_partial=report.was_partial,
        has_sufficient_evidence=has_sufficient_evidence,
        llm_call_count=llm_call_count,
        latency_ms=latency_ms,
        created_at=utcnow(),
    )
    session.add(row)
    await session.flush()
    return row


async def persist_trace(
    session: AsyncSession, answer_id: uuid.UUID, events: list[ag.TraceEvent]
) -> None:
    """Store the orchestration trace so §1.5 can replay it."""
    for event in events:
        session.add(
            AgentStep(
                id=uuid.uuid4(),
                answer_id=answer_id,
                sequence_number=event.sequence_number,
                step_type=event.step_type,
                duration_ms=event.duration_ms,
                payload=event.payload,
                created_at=utcnow(),
            )
        )
    await session.flush()


async def ask(
    session: AsyncSession, agent: AgentClient, user_id: uuid.UUID, request: AskRequest
) -> AskResponse:
    started = time.perf_counter()

    await ensure_corpus_indexed(agent)

    conversation = await resolve_conversation(
        session, user_id, request.conversation_id, request.question
    )
    history = await last_turn(session, conversation.id)

    result = await agent.sitrep(
        ag.SitrepRequest(
            question=request.question,
            conversation_id=str(conversation.id),
            document_ids=(
                [str(d) for d in request.document_ids] if request.document_ids else None
            ),
            conversation_history=history,
        )
    )

    report = mapping.map_situation_report(result)
    insufficient = mapping.map_insufficient_evidence(result)
    citations = await join_document_names(session, user_id, result.citations)
    latency_ms = int((time.perf_counter() - started) * 1000)

    row = await persist_answer(
        session,
        user_id=user_id,
        conversation_id=conversation.id,
        question=request.question,
        report=report,
        citations=citations,
        insufficient=insufficient,
        has_sufficient_evidence=result.has_sufficient_evidence,
        llm_call_count=result.llm_call_count,
        latency_ms=latency_ms,
    )

    return AskResponse(
        answer_id=row.id,
        conversation_id=conversation.id,
        situation_report=report,
        insufficient_evidence=insufficient,
        citations=citations,
        has_sufficient_evidence=result.has_sufficient_evidence,
        llm_call_count=result.llm_call_count,
        latency_ms=latency_ms,
    )
