"""The `/api/v1` router. One module per resource, mounted here."""

from fastapi import APIRouter

from app.api import agent_actions, ask, documents

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(ask.router)
api_router.include_router(documents.router)
api_router.include_router(agent_actions.router)
