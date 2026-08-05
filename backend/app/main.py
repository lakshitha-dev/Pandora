"""FastAPI application factory and entrypoint.

    python run.py                               # Windows — use this locally
    uvicorn app.main:app --reload --port 5000   # Linux / Azure App Service

Both serve http://localhost:5000/docs. See run.py for why Windows needs its own
entrypoint.
"""

import asyncio
import sys
import uuid
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


async def _bootstrap_dev_database() -> None:
    """Create tables and seed the corpus row on a non-Postgres URL.

    Alembic owns the schema on Postgres and its migrations use JSONB, which
    SQLite cannot run. This exists only so a laptop with no Postgres can still
    serve the app end to end; on Postgres it is skipped entirely.
    """
    settings = get_settings()
    if "postgresql" in settings.postgres_connection_string:
        return

    from sqlalchemy import select

    from app.db.base import Base, utcnow
    from app.db.models import CORPUS_DOCUMENT_ID, Document
    from app.db.session import get_engine, session_scope

    engine = get_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async for session in session_scope():
        exists = await session.scalar(
            select(Document.id).where(Document.id == CORPUS_DOCUMENT_ID)
        )
        if exists is None:
            session.add(
                Document(
                    id=CORPUS_DOCUMENT_ID,
                    user_id=uuid.UUID(int=0),
                    file_name="Pandora_RAG_Knowledge_2026.pdf",
                    content_type="application/pdf",
                    size_bytes=501366,
                    page_count=56,
                    chunk_count=195,
                    record_count=149,
                    status="indexed",
                    is_preloaded=True,
                    uploaded_at=utcnow(),
                    indexed_at=utcnow(),
                )
            )
    logger.warning("CONFIG: dev database bootstrapped (not Postgres — Alembic skipped).")


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    settings = get_settings()
    await _bootstrap_dev_database()
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
