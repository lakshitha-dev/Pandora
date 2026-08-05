"""Agent action persistence and resolution (API_CONTRACT §1.4–1.6).

Nothing executes without an explicit approval — the action is a record with a
status, and the approval gate is architectural, not a UI nicety.
"""

import uuid
from datetime import UTC

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import AgentAction, Answer
from app.schemas.agent_actions import AgentActionCreate, AgentActionUpdate, validate_payload

logger = get_logger(__name__)

RESOLVED_STATUSES = frozenset({"approved", "rejected", "completed"})


async def _citations_from_answer(
    session: AsyncSession, user_id: uuid.UUID, answer_id: uuid.UUID | None
) -> list[dict]:
    """Snapshot the evidence that justified the action.

    Copied rather than referenced: the audit trail has to survive the source
    document being deleted. The whole citation set of the source answer is taken —
    the §1.5 request body carries no `supporting_citations`, so the backend cannot
    narrow it without changing the frozen contract.
    """
    if answer_id is None:
        return []
    stmt = select(Answer).where(Answer.id == answer_id, Answer.user_id == user_id)
    answer = (await session.execute(stmt)).scalar_one_or_none()
    if answer is None:
        logger.info("action references unknown answer %s — storing no citations", answer_id)
        return []
    return [
        {
            "document_id": c.get("document_id"),
            "document_name": c.get("document_name"),
            "page": c.get("page"),
            "excerpt": c.get("excerpt"),
        }
        for c in (answer.citations or [])
    ]


async def create_action(
    session: AsyncSession, user_id: uuid.UUID, request: AgentActionCreate
) -> AgentAction:
    action = AgentAction(
        id=uuid.uuid4(),
        user_id=user_id,
        type=request.type,
        title=request.title,
        rationale=request.rationale,
        payload=request.payload,
        status="proposed",
        source_answer_id=request.source_answer_id,
        citations=await _citations_from_answer(session, user_id, request.source_answer_id),
        created_at=utcnow(),
    )
    session.add(action)
    await session.flush()
    return action


async def get_action(
    session: AsyncSession, user_id: uuid.UUID, action_id: uuid.UUID
) -> AgentAction:
    stmt = select(AgentAction).where(
        AgentAction.id == action_id, AgentAction.user_id == user_id
    )
    action = (await session.execute(stmt)).scalar_one_or_none()
    if action is None:
        raise errors.action_not_found(action_id)
    return action


async def list_actions(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: str | None = None,
    action_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AgentAction], int]:
    filters = [AgentAction.user_id == user_id]
    if status:
        filters.append(AgentAction.status == status)
    if action_type:
        filters.append(AgentAction.type == action_type)

    total = int(
        (await session.execute(select(func.count(AgentAction.id)).where(*filters))).scalar_one()
    )
    rows = (
        (
            await session.execute(
                select(AgentAction)
                .where(*filters)
                .order_by(AgentAction.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), total


async def resolve_action(
    session: AsyncSession, user_id: uuid.UUID, action_id: uuid.UUID, request: AgentActionUpdate
) -> AgentAction:
    action = await get_action(session, user_id, action_id)
    if action.status in RESOLVED_STATUSES:
        raise errors.action_already_resolved(action_id)

    if request.payload is not None:
        # The user edited a drafted email before approving it.
        try:
            action.payload = validate_payload(action.type, request.payload)
        except ValueError as exc:
            raise errors.invalid_request(str(exc)) from exc

    action.status = request.status
    if request.note is not None:
        action.note = request.note
    action.resolved_at = utcnow()
    await session.flush()
    return action


def as_utc(action: AgentAction) -> AgentAction:
    """Postgres returns tz-aware datetimes; SQLite (tests) returns naive ones."""
    if action.created_at is not None and action.created_at.tzinfo is None:
        action.created_at = action.created_at.replace(tzinfo=UTC)
    if action.resolved_at is not None and action.resolved_at.tzinfo is None:
        action.resolved_at = action.resolved_at.replace(tzinfo=UTC)
    return action
