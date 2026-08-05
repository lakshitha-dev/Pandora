"""Past situation reports (API_CONTRACT §1.5).

Reads only. The rows were written by `/ask` or by the SSE endpoint; nothing here
re-runs retrieval or calls the agent.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.db.models import AgentStep, Answer
from app.schemas.ask import AskResponse, InsufficientEvidence, SituationReport
from app.schemas.common import Citation
from app.schemas.situation_reports import (
    SituationReportDetail,
    SituationReportListResponse,
    SituationReportSummary,
    TraceStep,
)


async def list_reports(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    priority_class: str | None = None,
    had_conflict: bool | None = None,
    was_insufficient: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> SituationReportListResponse:
    """Filters hit indexed scalar columns, never the stored JSON."""
    conditions = [Answer.user_id == user_id]
    if priority_class is not None:
        conditions.append(Answer.priority_class == priority_class)
    if had_conflict is not None:
        conditions.append(Answer.had_conflict.is_(had_conflict))
    if was_insufficient is not None:
        conditions.append(Answer.has_sufficient_evidence.is_(not was_insufficient))

    total = await session.scalar(
        select(func.count()).select_from(Answer).where(*conditions)
    )

    rows = (
        await session.execute(
            select(Answer)
            .where(*conditions)
            .order_by(Answer.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()

    return SituationReportListResponse(
        reports=[
            SituationReportSummary(
                answer_id=row.id,
                question=row.question,
                priority_class=row.priority_class,
                assembly_mode=row.assembly_mode,
                confidence_level=row.confidence,
                affected_region_ids=list(row.affected_region_ids or []),
                citation_count=len(row.citations or []),
                had_conflict=row.had_conflict,
                was_insufficient=not row.has_sufficient_evidence,
                was_partial=row.was_partial,
                created_at=row.created_at,
            )
            for row in rows
        ],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


async def get_report(
    session: AsyncSession, user_id: uuid.UUID, answer_id: uuid.UUID
) -> SituationReportDetail:
    """The full §1.1 body plus the persisted trace, for replay."""
    row = (
        await session.execute(
            select(Answer).where(Answer.id == answer_id, Answer.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise errors.report_not_found(answer_id)

    steps = (
        await session.execute(
            select(AgentStep)
            .where(AgentStep.answer_id == row.id)
            .order_by(AgentStep.sequence_number)
        )
    ).scalars().all()

    base = AskResponse(
        answer_id=row.id,
        conversation_id=row.conversation_id,
        situation_report=SituationReport.model_validate(row.situation_report or {}),
        insufficient_evidence=(
            InsufficientEvidence.model_validate(row.insufficient_evidence)
            if row.insufficient_evidence
            else None
        ),
        citations=[Citation.model_validate(c) for c in (row.citations or [])],
        has_sufficient_evidence=row.has_sufficient_evidence,
        llm_call_count=row.llm_call_count,
        latency_ms=row.latency_ms,
    )

    return SituationReportDetail(
        **base.model_dump(by_alias=True),
        trace=[
            TraceStep(
                step_type=s.step_type,
                sequence_number=s.sequence_number,
                duration_ms=s.duration_ms,
                payload=s.payload or {},
            )
            for s in steps
        ],
    )
