"""`POST /api/v1/ask` — the core endpoint (API_CONTRACT §1.1).

Router stays thin: parse, delegate, return.
"""

from fastapi import APIRouter, status

from app.core.dependencies import AgentDep, DbSession, UserDep
from app.schemas.ask import AskRequest, AskResponse
from app.schemas.common import ErrorEnvelope
from app.services import ask as ask_service

router = APIRouter(tags=["ask"])


@router.post(
    "/ask",
    response_model=AskResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a question of your documents",
    responses={
        401: {"model": ErrorEnvelope},
        422: {"model": ErrorEnvelope, "description": "no_documents_indexed"},
        502: {"model": ErrorEnvelope, "description": "agent_service_unavailable"},
        504: {"model": ErrorEnvelope, "description": "agent_service_timeout"},
    },
)
async def ask(
    request: AskRequest, session: DbSession, agent: AgentDep, user: UserDep
) -> AskResponse:
    return await ask_service.ask(session, agent, user.id, request)
