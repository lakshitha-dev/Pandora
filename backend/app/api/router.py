"""The `/api/v1` router. One module per resource, mounted here."""

from fastapi import APIRouter

from app.api import ask, ask_stream, documents, incidents, situation_reports

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(ask.router)
api_router.include_router(ask_stream.router)
api_router.include_router(documents.router)
api_router.include_router(situation_reports.router)
api_router.include_router(incidents.router)
