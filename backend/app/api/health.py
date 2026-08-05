"""`GET /health` — the Azure App Service probe. No auth, no `/api/v1` prefix.

Always returns 200 so a slow dependency doesn't get the container recycled; the
body says what is actually reachable.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.core.dependencies import AgentDep, DbSession, SettingsDep
from app.core.logging import get_logger

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


class HealthResponse(BaseModel):
    status: str
    database_reachable: bool
    agent_service_reachable: bool
    agent_service_status: str
    # §2.4's single most important field, surfaced: false means no query can
    # work, and /ask should say so rather than let the model answer from
    # pretrained knowledge.
    corpus_indexed: bool
    version: str
    mode: str


@router.get("/health", response_model=HealthResponse, summary="Liveness and dependency check")
async def health(session: DbSession, agent: AgentDep, settings: SettingsDep) -> HealthResponse:
    try:
        await session.execute(text("SELECT 1"))
        database_reachable = True
    except Exception as exc:  # noqa: BLE001 — the probe reports, it doesn't raise
        logger.warning("health: database unreachable: %s", exc)
        database_reachable = False

    agent_health = await agent.health()
    agent_reachable = agent_health.status == "ok"

    return HealthResponse(
        status="ok" if database_reachable and agent_reachable else "degraded",
        database_reachable=database_reachable,
        agent_service_reachable=agent_reachable,
        agent_service_status=agent_health.status,
        corpus_indexed=agent_health.corpus_indexed,
        version=settings.version,
        mode=settings.environment_mode,
    )
