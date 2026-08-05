"""Supabase JWT verification — signature and expiry, at the gateway only.

Nothing downstream handles auth. The agent service is not publicly routable and
uses a shared secret instead (`X-Internal-Key`).
"""

import uuid
from dataclasses import dataclass

from jose import JWTError, jwt

from app.core import errors
from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    email: str | None


def _parse_user_id(raw: str | None) -> uuid.UUID:
    if not raw:
        raise errors.unauthenticated("Token is missing a subject claim.")
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise errors.unauthenticated("Token subject is not a valid user id.") from exc


def verify_token(token: str, settings: Settings) -> CurrentUser:
    """Decode and validate a Supabase access token. Raises AppError(401) on any failure."""
    if not settings.supabase_jwt_secret:
        logger.error("SUPABASE_JWT_SECRET is not configured; rejecting request.")
        raise errors.unauthenticated("Authentication is not configured on the server.")

    try:
        claims = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=[settings.supabase_jwt_algorithm],
            audience=settings.supabase_jwt_audience or None,
            options={"verify_aud": bool(settings.supabase_jwt_audience)},
        )
    except JWTError as exc:
        # Expired, bad signature, wrong audience — all one answer to the client.
        raise errors.unauthenticated("Token is invalid or has expired.") from exc

    return CurrentUser(id=_parse_user_id(claims.get("sub")), email=claims.get("email"))


def dev_user(settings: Settings) -> CurrentUser:
    """The fixed identity used when AUTH_DISABLED=true."""
    return CurrentUser(id=uuid.UUID(settings.dev_user_id), email="dev@localhost")
