"""FastAPI application factory and entrypoint.

    python run.py                               # Windows — use this locally
    uvicorn app.main:app --reload --port 5000   # Linux / Azure App Service

Both serve http://localhost:5000/docs. See run.py for why Windows needs its own
entrypoint.
"""

import asyncio
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger, register_request_logging
from app.db.session import dispose_engine
from app.services.agent_client import AgentClient

logger = get_logger(__name__)


def _use_selector_event_loop_on_windows() -> None:
    """psycopg's async mode cannot run on Windows' default ProactorEventLoop.

    Without a selector loop, every DB query on a Windows dev machine dies with
    `InterfaceError: Psycopg cannot use the 'ProactorEventLoop'`. This covers
    hosts that import the module before starting a loop; `uvicorn app.main:app`
    is *not* one of them — it builds its loop first, which is what run.py fixes.
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


_use_selector_event_loop_on_windows()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    settings = get_settings()
    client = AgentClient(settings)
    await client.start()
    app.state.agent_client = client

    for warning in settings.startup_warnings():
        logger.warning("CONFIG: %s", warning)
    logger.info(
        "%s v%s ready — agent=%s mode=%s",
        settings.app_name,
        settings.version,
        settings.agent_service_url,
        settings.environment_mode,
    )

    yield

    await client.close()
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description=(
            "Gateway for the SME Business Intelligence Assistant. "
            "Implements docs/API_CONTRACT.md Part 1. The browser talks only to this service."
        ),
        lifespan=lifespan,
    )

    # Configure CORS now, don't debug it at 2am.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["X-Request-ID"],
    )

    register_request_logging(app)
    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_router)
    return app


app = create_app()
