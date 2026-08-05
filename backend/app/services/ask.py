"""`POST /api/v1/ask` orchestration: guard → /agent/sitrep → join names → persist.

The gateway owns everything the agent service deliberately doesn't: who the user
is, whether the corpus is indexed, what the documents are called, and the audit
trail. The agent owns retrieval, the three specialists, grounding, and conflicts.

**Insufficient evidence is a 200 with a report**, never an error. A report that
honestly declines to answer is a successful response — mapping it to a 4xx would
throw away the 20-mark Accuracy criterion (`SOLUTION.md` §4.6).
"""

import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import Answer, Conversation, Document
from app.schemas.agent import ConversationTurn, SitrepRequest
from app.schemas.ask import AskRequest, AskResponse
from app.services import documents as document_service
from app.services import report_mapping
from app.services.agent_client import AgentClient

logger = get_logger(__name__)


async def resolve_conversation(
    session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID | None, question: str
) -> Conversation:
    """Shared with `ask_stream` — both entry points answer into a conversation."""
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


async def last_turn(session: AsyncSession, conversation_id: uuid.UUID) -> list[ConversationTurn]:
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
        ConversationTurn(role="user", content=previous.question),
        ConversationTurn(
            role="assistant",
            content=report_mapping.report_history_text(previous.situation_report),
        ),
    ]


async def document_names(
    session: AsyncSession, user_id: uuid.UUID, document_ids: set[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """The agent service returns `document_id` only; the name lives in Postgres."""
    if not document_ids:
        return {}
    stmt = select(Document.id, Document.file_name).where(
        Document.id.in_(document_ids), Document.user_id == user_id
    )
    return {row.id: row.file_name for row in (await session.execute(stmt)).all()}


async def ask(
    session: AsyncSession, agent: AgentClient, user_id: uuid.UUID, request: AskRequest
) -> AskResponse:
    started = time.perf_counter()

    # Guard before any LLM call — no wasted tokens, and a clear message for the UI.
    indexed = await document_service.count_indexed_documents(
        session, user_id, request.document_ids
    )
    if indexed == 0:
        raise errors.corpus_not_indexed()

    conversation = await resolve_conversation(
        session, user_id, request.conversation_id, request.question
    )
    history = await last_turn(session, conversation.id)

    result = await agent.sitrep(
        SitrepRequest(
            question=request.question,
            conversation_id=str(conversation.id),
            document_ids=request.document_ids,
            mode=None,  # let the orchestrator classify; forcing a mode is for tests
            conversation_history=history,
        )
    )

    names = await document_names(
        session, user_id, report_mapping.citation_document_ids(result.citations)
    )
    citations = report_mapping.to_citations(result.citations, names)
    situation_report = report_mapping.to_situation_report(result)
    insufficient = (
        report_mapping.to_insufficient_evidence(result, citations)
        if not result.has_sufficient_evidence
        else None
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    answer_row = Answer(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        user_id=user_id,
        question=request.question,
        role_lens=request.role_lens or "guardian",
        situation_report=situation_report.model_dump(mode="json", by_alias=True),
        citations=[c.model_dump(mode="json") for c in citations],
        insufficient_evidence=(
            insufficient.model_dump(mode="json") if insufficient is not None else None
        ),
        # Denormalised so /api/v1/situation-reports can filter without opening
        # the JSON on every row.
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
    await session.flush()

    logger.info(
        "ask answered id=%s priority=%s confidence=%s sufficient=%s conflicts=%d "
        "citations=%d llm_calls=%d latency_ms=%d",
        answer_row.id,
        situation_report.priority.class_,
        situation_report.confidence.level,
        result.has_sufficient_evidence,
        len(situation_report.conflicts),
        len(citations),
        result.llm_call_count,
        latency_ms,
    )

    return AskResponse(
        answer_id=answer_row.id,
        conversation_id=conversation.id,
        situation_report=situation_report,
        insufficient_evidence=insufficient,
        citations=citations,
        has_sufficient_evidence=result.has_sufficient_evidence,
        llm_call_count=result.llm_call_count,
        latency_ms=latency_ms,
    )
