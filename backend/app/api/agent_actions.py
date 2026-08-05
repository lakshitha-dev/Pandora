"""`/api/v1/agent-actions` — the approval gate (API_CONTRACT §1.4–1.6)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.dependencies import DbSession, UserDep
from app.schemas.agent_actions import (
    AgentActionCreate,
    AgentActionListResponse,
    AgentActionOut,
    AgentActionUpdate,
)
from app.schemas.common import ActionStatus, ActionType, ErrorEnvelope
from app.services import agent_actions as action_service

router = APIRouter(prefix="/agent-actions", tags=["agent-actions"])


@router.get(
    "",
    response_model=AgentActionListResponse,
    summary="List agent actions",
    responses={401: {"model": ErrorEnvelope}},
)
async def list_actions(
    session: DbSession,
    user: UserDep,
    status_filter: Annotated[ActionStatus | None, Query(alias="status")] = None,
    type_filter: Annotated[ActionType | None, Query(alias="type")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AgentActionListResponse:
    rows, total = await action_service.list_actions(
        session,
        user.id,
        status=status_filter,
        action_type=type_filter,
        limit=limit,
        offset=offset,
    )
    return AgentActionListResponse(
        actions=[AgentActionOut.model_validate(action_service.as_utc(row)) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=AgentActionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Accept a suggested action — persists it as `proposed`",
    responses={400: {"model": ErrorEnvelope}, 401: {"model": ErrorEnvelope}},
)
async def create_action(
    request: AgentActionCreate, session: DbSession, user: UserDep
) -> AgentActionOut:
    action = await action_service.create_action(session, user.id, request)
    return AgentActionOut.model_validate(action_service.as_utc(action))


@router.get(
    "/{action_id}",
    response_model=AgentActionOut,
    summary="Get one agent action",
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def get_action(action_id: uuid.UUID, session: DbSession, user: UserDep) -> AgentActionOut:
    action = await action_service.get_action(session, user.id, action_id)
    return AgentActionOut.model_validate(action_service.as_utc(action))


@router.patch(
    "/{action_id}",
    response_model=AgentActionOut,
    summary="Approve, reject or complete an action",
    responses={
        400: {"model": ErrorEnvelope},
        401: {"model": ErrorEnvelope},
        404: {"model": ErrorEnvelope},
        409: {"model": ErrorEnvelope, "description": "action_already_resolved"},
    },
)
async def resolve_action(
    action_id: uuid.UUID, request: AgentActionUpdate, session: DbSession, user: UserDep
) -> AgentActionOut:
    action = await action_service.resolve_action(session, user.id, action_id, request)
    return AgentActionOut.model_validate(action_service.as_utc(action))
