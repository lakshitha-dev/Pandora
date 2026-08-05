"""`/api/v1/ask` orchestration: guard → /rag/query → join names → /agent/run → persist.

The gateway owns everything the agent service deliberately doesn't: who the user
is, whether they have anything indexed, what the documents are called, and the
audit trail.
"""

import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import Answer, Conversation, Document
from app.schemas.agent import (
    AgentRunCitation,
    AgentRunRequest,
    ConversationTurn,
    RagQueryRequest,
    RagQueryResponse,
)
from app.schemas.ask import AskRequest, AskResponse, SuggestedAction
from app.schemas.common import Citation
from app.services import documents as document_service
from app.services.agent_client import AgentClient

logger = get_logger(__name__)

UNKNOWN_DOCUMENT_NAME = "(document unavailable)"


async def _resolve_conversation(
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


async def _last_turn(session: AsyncSession, conversation_id: uuid.UUID) -> list[ConversationTurn]:
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
        ConversationTurn(role="assistant", content=previous.answer),
    ]


async def _join_document_names(
    session: AsyncSession, user_id: uuid.UUID, rag: RagQueryResponse
) -> list[Citation]:
    """The agent service returns `document_id` only; the name lives in Postgres."""
    document_ids = {c.document_id for c in rag.citations}
    names: dict[uuid.UUID, str] = {}
    if document_ids:
        stmt = select(Document.id, Document.file_name).where(
            Document.id.in_(document_ids), Document.user_id == user_id
        )
        names = {row.id: row.file_name for row in (await session.execute(stmt)).all()}

    citations: list[Citation] = []
    for c in rag.citations:
        name = names.get(c.document_id)
        if name is None:
            # Keep the citation: dropping it would break the [n] markers already
            # written into the answer text.
            logger.warning("citation references unknown document %s", c.document_id)
            name = UNKNOWN_DOCUMENT_NAME
        citations.append(
            Citation(
                marker=c.marker,
                document_id=c.document_id,
                document_name=name,
                page=c.page,
                section=c.section,
                excerpt=c.excerpt,
                relevance_score=max(0.0, min(1.0, c.relevance_score)),
            )
        )
    return citations


async def _propose_action(
    agent: AgentClient, question: str, rag: RagQueryResponse
) -> SuggestedAction | None:
    """Ask the agent service whether an action is warranted.

    Skipped when there is no grounded evidence — an action nothing supports is
    exactly what the approval gate exists to prevent, and it saves an LLM call.
    A failure here degrades to `null`: a good cited answer should not become a
    502 because the action step had a bad minute.
    """
    if not rag.has_sufficient_evidence or not rag.citations:
        return None
    try:
        result = await agent.run_agent(
            AgentRunRequest(
                question=question,
                answer=rag.answer,
                citations=[
                    AgentRunCitation(
                        marker=c.marker, document_id=c.document_id, excerpt=c.excerpt
                    )
                    for c in rag.citations
                ],
            )
        )
    except errors.AppError as exc:
        logger.warning("agent/run failed (%s) — returning the answer with no action", exc.code)
        return None

    if result.suggested_action is None:
        return None
    action = result.suggested_action
    return SuggestedAction(
        type=action.type,
        title=action.title,
        rationale=action.rationale,
        payload=action.payload,
        supporting_citations=action.supporting_citations,
    )


async def ask(
    session: AsyncSession, agent: AgentClient, user_id: uuid.UUID, request: AskRequest
) -> AskResponse:
    started = time.perf_counter()

    # Guard before any LLM call — no wasted tokens, and a clear message for the UI.
    indexed = await document_service.count_indexed_documents(
        session, user_id, request.document_ids
    )
    if indexed == 0:
        raise errors.no_documents_indexed()

    conversation = await _resolve_conversation(
        session, user_id, request.conversation_id, request.question
    )
    history = await _last_turn(session, conversation.id)

    rag = await agent.query(
        RagQueryRequest(
            question=request.question,
            document_ids=request.document_ids,
            top_k=6,
            conversation_history=history,
        )
    )

    citations = await _join_document_names(session, user_id, rag)
    suggested_action = await _propose_action(agent, request.question, rag)
    latency_ms = int((time.perf_counter() - started) * 1000)

    answer_row = Answer(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        user_id=user_id,
        question=request.question,
        answer=rag.answer,
        citations=[c.model_dump(mode="json") for c in citations],
        confidence=rag.confidence,
        has_sufficient_evidence=rag.has_sufficient_evidence,
        latency_ms=latency_ms,
        created_at=utcnow(),
    )
    session.add(answer_row)
    await session.flush()

    return AskResponse(
        answer_id=answer_row.id,
        conversation_id=conversation.id,
        answer=rag.answer,
        citations=citations,
        suggested_action=suggested_action,
        confidence=rag.confidence,
        has_sufficient_evidence=rag.has_sufficient_evidence,
        latency_ms=latency_ms,
    )
