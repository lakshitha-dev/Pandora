"""Pandora Knowledge Guardian — agent service.

RAG + agentic layer. Called only by the backend gateway, never by the
browser. Auth is a shared secret header, not a user JWT.

    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.routers import agent, health, rag

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
# The Azure SDK logs every request header at INFO — far too noisy.
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Pandora Knowledge Guardian — Agent Service",
    description=(
        "Record-aware RAG over the Pandora corpus, with grounded generation "
        "validated against the corpus's own §15.2 Retrieval Grounding Rules."
    ),
    version=health.VERSION,
)

# Paths that do not require the internal key.
_OPEN_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/"}


@app.middleware("http")
async def require_internal_key(request: Request, call_next):
    """Shared-secret gate.

    The agent service is not publicly routable, but defence in depth is
    cheap. /health stays open so Azure App Service probes work.
    """
    path = request.url.path
    if path in _OPEN_PATHS or path.startswith(("/docs", "/redoc", "/openapi")):
        return await call_next(request)

    provided = request.headers.get("X-Internal-Key")
    if provided != settings.agent_service_key:
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "unauthenticated",
                    "message": "missing or invalid X-Internal-Key header",
                }
            },
        )
    return await call_next(request)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Always return the standard error envelope, never a bare 500 page."""
    logger.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_error", "message": str(exc)[:300]}},
    )


app.include_router(health.router)
app.include_router(rag.router)
app.include_router(agent.router)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "service": "pandora-agent",
        "version": health.VERSION,
        "docs": "/docs",
        "health": "/health",
    }


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("agent service starting")
    logger.info("  chat deployment      : %s", settings.azure_openai_chat_deployment)
    logger.info("  embedding deployment : %s", settings.azure_openai_embedding_deployment)
    logger.info("  reasoning model      : %s", settings.is_reasoning_model)
    logger.info("  search index         : %s", settings.azure_search_index_name)
    logger.info("  agentic enabled      : %s", settings.agentic_enabled)
    logger.info(
        "  agent budgets        : %ss/specialist, %ss total, %d LLM calls, %d retry",
        settings.agent_timeout_seconds,
        settings.orchestration_budget_seconds,
        settings.max_llm_calls_per_query,
        settings.max_retries,
    )
