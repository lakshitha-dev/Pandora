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
    summary="Ask a question and get a cited Situation Report",
    responses={
        401: {"model": ErrorEnvelope},
        422: {"model": ErrorEnvelope, "description": "corpus_not_indexed"},
        502: {"model": ErrorEnvelope, "description": "agent_service_unavailable"},
        504: {"model": ErrorEnvelope, "description": "agent_service_timeout"},
    },
)
async def ask(
    request: AskRequest, session: DbSession, agent: AgentDep, user: UserDep
) -> AskResponse:
    return await ask_service.ask(session, agent, user.id, request)
