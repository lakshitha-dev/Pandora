"""`GET /api/v1/incidents` — the incident register (API_CONTRACT §1.6).

A filtered projection of metadata already in the index. No retrieval work and no
LLM call, so it stays cheap enough to page through.
"""

from fastapi import APIRouter, Query

from app.core.dependencies import AgentDep, UserDep
from app.schemas.common import ErrorEnvelope
from app.schemas.incidents import Incident, IncidentListResponse, RiskLevel

router = APIRouter(tags=["incidents"])


@router.get(
    "/incidents",
    response_model=IncidentListResponse,
    summary="List incident records from the corpus",
    responses={
        401: {"model": ErrorEnvelope},
        502: {"model": ErrorEnvelope, "description": "agent_service_unavailable"},
    },
)
async def list_incidents(
    agent: AgentDep,
    user: UserDep,
    risk_level: RiskLevel | None = None,
    region_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> IncidentListResponse:
    result = await agent.incidents(
        risk_level=risk_level, region_id=region_id, limit=limit, offset=offset
    )
    return IncidentListResponse(
        incidents=[
            Incident(
                record_id=i.record_id,
                title=i.title,
                region_id=i.region_id,
                region_name=i.region_name,
                risk_level=i.risk_level,
                chapter=i.chapter,
                page=i.page,
                summary_excerpt=i.summary_excerpt,
                evidence_quality=i.evidence_quality,
            )
            for i in result.incidents
        ],
        total=result.total,
        limit=result.limit,
        offset=result.offset,
    )
