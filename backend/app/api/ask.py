"""`POST /api/v1/ask` and `GET /api/v1/ask/stream` (API_CONTRACT §1.1, §1.2).

Returns a grounded Situation Report with its citations and confidence. An
insufficient-evidence report is a `200` like any other — see §1.4.

Router stays thin: parse, delegate, return.
"""

from uuid import UUID

from fastapi import APIRouter, Query, status
from sse_starlette.sse import EventSourceResponse

from app.core import errors
from app.core.dependencies import AgentDep, DbSession, SettingsDep, UserDep
from app.core.security import CurrentUser, dev_user, verify_token
from app.schemas.ask import AskRequest, AskResponse
from app.schemas.common import ErrorEnvelope, RoleLens
from app.services import ask as ask_service
from app.services import ask_stream as ask_stream_service

router = APIRouter(tags=["ask"])


@router.post(
    "/ask",
    response_model=AskResponse,
    status_code=status.HTTP_200_OK,
    summary="Describe an incident, get a cited Situation Report",
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


@router.get(
    "/ask/stream",
    summary="Stream the orchestration trace as it happens (SSE)",
    response_class=EventSourceResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": (
                "§1.2 trace events. Terminal event is `answer.completed`, whose payload is "
                "the complete §1.1 body — a client can use this endpoint alone."
            ),
        },
        401: {"model": ErrorEnvelope},
        422: {"model": ErrorEnvelope, "description": "corpus_not_indexed"},
    },
)
async def ask_stream(
    session: DbSession,
    agent: AgentDep,
    settings: SettingsDep,
    question: str = Query(min_length=1, max_length=2000),
    conversation_id: UUID | None = None,
    document_ids: list[UUID] | None = Query(default=None),
    role_lens: RoleLens | None = None,
    access_token: str | None = Query(
        default=None,
        description="Supabase JWT. `EventSource` cannot set headers, so this endpoint "
        "takes the token as a query param and validates it identically.",
    ),
) -> EventSourceResponse:
    user = _user_from_query(access_token, settings)
    request = AskRequest(
        question=question,
        conversation_id=conversation_id,
        document_ids=document_ids,
        role_lens=role_lens,
    )
    # Guards run here, before the response starts, so `401` and `422` are real
    # HTTP statuses with the error envelope. Anything after this is an event.
    context = await ask_stream_service.prepare(session, user.id, request)

    return EventSourceResponse(
        ask_stream_service.stream(agent, user.id, request, context),
        # Nginx and App Service will happily buffer an event stream into
        # uselessness. §1.2 says the gateway MUST NOT buffer.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _user_from_query(access_token: str | None, settings: SettingsDep) -> CurrentUser:
    if settings.auth_disabled:
        return dev_user(settings)
    if not access_token:
        raise errors.unauthenticated("Missing `access_token` query parameter.")
    return verify_token(access_token, settings)
