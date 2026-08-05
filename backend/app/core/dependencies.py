"""FastAPI dependencies — settings, DB session, current user, agent client.

Shared concerns are injected, never reached for as globals.
"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.core.config import Settings, get_settings
from app.core.security import CurrentUser, dev_user, verify_token
from app.db.session import session_scope
from app.services.agent_client import AgentClient

# auto_error=False so a missing header raises our envelope, not FastAPI's default body.
_bearer = HTTPBearer(auto_error=False)


def settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(settings_dep)]


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in session_scope():
        yield session


DbSession = Annotated[AsyncSession, Depends(db_session)]


def agent_client(request: Request) -> AgentClient:
    client: AgentClient | None = getattr(request.app.state, "agent_client", None)
    if client is None:
        raise errors.agent_service_unavailable("The agent client is not initialised.")
    return client


AgentDep = Annotated[AgentClient, Depends(agent_client)]


async def current_user(
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> CurrentUser:
    if settings.auth_disabled:
        return dev_user(settings)
    if credentials is None or not credentials.credentials:
        raise errors.unauthenticated("Missing Authorization: Bearer <token> header.")
    return verify_token(credentials.credentials, settings)


UserDep = Annotated[CurrentUser, Depends(current_user)]


async def current_user_from_query(
    settings: SettingsDep,
    access_token: str | None = None,
) -> CurrentUser:
    """Auth for `GET /api/v1/ask/stream` only.

    `EventSource` cannot set request headers, so the JWT arrives as a query
    param on this one endpoint. It is validated identically — same secret, same
    audience, same expiry — and `AUTH_DISABLED` is honoured the same way, so
    this is a different transport for the token, not a weaker check.
    """
    if settings.auth_disabled:
        return dev_user(settings)
    if not access_token:
        raise errors.unauthenticated("Missing access_token query parameter.")
    return verify_token(access_token, settings)


StreamUserDep = Annotated[CurrentUser, Depends(current_user_from_query)]
