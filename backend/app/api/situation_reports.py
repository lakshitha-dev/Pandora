"""`GET /api/v1/situation-reports` — past reports (API_CONTRACT §1.5).

Backs `/app/investigations`. Router stays thin: parse, delegate, return.
"""

from uuid import UUID

from fastapi import APIRouter, Query

from app.core.dependencies import DbSession, UserDep
from app.schemas.common import ErrorEnvelope, PriorityClass
from app.schemas.situation_reports import (
    SituationReportDetail,
    SituationReportListResponse,
)
from app.services import situation_reports as service

router = APIRouter(tags=["situation-reports"])


@router.get(
    "/situation-reports",
    response_model=SituationReportListResponse,
    summary="List past situation reports",
    responses={401: {"model": ErrorEnvelope}},
)
async def list_situation_reports(
    session: DbSession,
    user: UserDep,
    priority_class: PriorityClass | None = None,
    had_conflict: bool | None = None,
    was_insufficient: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SituationReportListResponse:
    return await service.list_reports(
        session,
        user.id,
        priority_class=priority_class,
        had_conflict=had_conflict,
        was_insufficient=was_insufficient,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/situation-reports/{answer_id}",
    response_model=SituationReportDetail,
    summary="One past report, with its orchestration trace for replay",
    responses={
        401: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope, "description": "report_not_found"},
    },
)
async def get_situation_report(
    answer_id: UUID, session: DbSession, user: UserDep
) -> SituationReportDetail:
    return await service.get_report(session, user.id, answer_id)
