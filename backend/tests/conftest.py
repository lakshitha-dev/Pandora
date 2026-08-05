"""Test harness: SQLite in-memory, stub agent, auth disabled.

The env vars are set before `app` is imported — `get_settings()` is cached, so
anything set afterwards is ignored.
"""

import os
from collections.abc import AsyncGenerator

os.environ.update(
    {
        "POSTGRES_CONNECTION_STRING": "sqlite+aiosqlite:///:memory:",
        "AUTH_DISABLED": "true",
        "AGENT_STUB_MODE": "true",
        "LOG_LEVEL": "WARNING",
    }
)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db import session as db_session_module  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import Document  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest_asyncio.fixture
async def engine():  # noqa: ANN201
    """One in-memory database shared by every connection in the test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    # Point both the request dependency and the background tasks at it.
    db_session_module._engine = engine
    db_session_module._session_factory = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False
    )
    yield engine
    db_session_module._engine = None
    db_session_module._session_factory = None
    await engine.dispose()


@pytest_asyncio.fixture
async def client(engine) -> AsyncGenerator[AsyncClient, None]:  # noqa: ANN001
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        async with app.router.lifespan_context(app):
            yield http_client


@pytest.fixture(autouse=True)
def _reset_sse_exit_event():  # noqa: ANN202
    """sse-starlette caches a shutdown Event on the loop that first used it.

    pytest-asyncio hands every test a fresh loop, so the second streaming test
    would otherwise die with "bound to a different event loop". Clearing it
    between tests is a harness concern only — under uvicorn there is one loop.
    """
    from sse_starlette.sse import AppStatus

    AppStatus.should_exit_event = None
    yield
    AppStatus.should_exit_event = None


@pytest.fixture
def settings():  # noqa: ANN201
    return get_settings()


@pytest.fixture
def user_id(settings):  # noqa: ANN001, ANN201
    import uuid

    return uuid.UUID(settings.dev_user_id)


@pytest_asyncio.fixture
async def indexed_document(engine, user_id):  # noqa: ANN001, ANN201
    """The preloaded corpus, indexed — so /ask gets past the 422 guard.

    The id is the one the stub agent cites in every §1.1 fixture, so
    `document_name` actually joins.
    """
    import uuid

    from app.db.base import utcnow

    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    document = Document(
        id=uuid.UUID("1a2b3c4d-2222-4e5f-9a8b-7c6d5e4f3a2b"),
        user_id=user_id,
        file_name="Pandora_RAG_Knowledge_2026.pdf",
        content_type="application/pdf",
        size_bytes=1284910,
        page_count=56,
        chunk_count=221,
        status="indexed",
        uploaded_at=utcnow(),
        indexed_at=utcnow(),
    )
    async with factory() as session:
        session.add(document)
        await session.commit()
    return document
