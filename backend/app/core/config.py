"""Settings, read from the environment once and validated at startup.

One place, validated at import of `get_settings()`. No scattered `os.getenv()`.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_name: str = "SME Business Intelligence Assistant — Gateway"
    version: str = "0.1.0"
    log_level: str = "INFO"

    # --- Database ---
    postgres_connection_string: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/sme_assistant"
    )
    db_echo: bool = False

    # --- Auth ---
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    supabase_jwt_algorithm: str = "HS256"
    supabase_jwt_audience: str = "authenticated"
    auth_disabled: bool = False
    dev_user_id: str = "00000000-0000-4000-8000-000000000001"

    # --- Agent service ---
    agent_service_url: str = "http://localhost:8000"
    agent_service_key: str = ""
    agent_stub_mode: bool = False
    agent_query_timeout_seconds: float = 30.0
    agent_ingest_timeout_seconds: float = 60.0
    agent_health_timeout_seconds: float = 3.0

    # --- CORS ---
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # --- Uploads ---
    max_upload_bytes: int = 10 * 1024 * 1024
    allowed_content_types: str = (
        "application/pdf,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "text/csv,"
        "text/plain"
    )

    @field_validator("postgres_connection_string")
    @classmethod
    def _require_async_driver(cls, value: str) -> str:
        """SQLAlchemy's async engine needs an async driver in the URL."""
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_content_type_set(self) -> set[str]:
        return {ct.strip() for ct in self.allowed_content_types.split(",") if ct.strip()}

    @property
    def environment_mode(self) -> Literal["stub", "live"]:
        return "stub" if self.agent_stub_mode else "live"

    def startup_warnings(self) -> list[str]:
        """Configuration that is legal but must not reach production silently."""
        warnings: list[str] = []
        if self.auth_disabled:
            warnings.append(
                "AUTH_DISABLED=true — every request runs as the dev user. "
                "Do not deploy with this set."
            )
        elif not self.supabase_jwt_secret:
            warnings.append(
                "SUPABASE_JWT_SECRET is empty and AUTH_DISABLED is false — "
                "every authenticated request will return 401."
            )
        if self.agent_stub_mode:
            warnings.append(
                "AGENT_STUB_MODE=true — /ask and ingestion return contract fixtures, "
                "the agent service is never called."
            )
        elif not self.agent_service_key:
            warnings.append(
                "AGENT_SERVICE_KEY is empty — the agent service will reject X-Internal-Key."
            )
        return warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings_field = Field  # re-exported for convenience in dependencies
