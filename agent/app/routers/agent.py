"""POST /agent/sitrep — the orchestrated path (docs/API_CONTRACT.md §2.3).

Classifies, routes, dispatches specialists concurrently, validates, and
streams. Layer 5 uses this; Layers 1-2 do not.

    Accept: text/event-stream  -> streams the §1.2 trace events
    Accept: application/json   -> the assembled report in one response

Both modes run the *same* orchestrator over the same emitter. A JSON caller
simply never drains the queue, so there is no second code path to keep in
sync — and no way for the streaming and non-streaming reports to diverge.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.agents.orchestrator import run_sitrep
from app.agents.trace import TraceEmitter
from app.models.schemas import SitrepRequest, SitrepResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["agent"])


def _wants_stream(request: Request) -> bool:
    return "text/event-stream" in request.headers.get("accept", "").lower()


@router.post("/agent/sitrep", response_model=SitrepResponse)
async def sitrep(req: SitrepRequest, request: Request):
    """Assemble a Situation Report, streaming the orchestration if asked."""
    emitter = TraceEmitter()

    if not _wants_stream(request):
        return await run_sitrep(req, emitter)

    task = asyncio.create_task(run_sitrep(req, emitter))

    async def events():
        try:
            async for frame in emitter.stream():
                yield frame
        finally:
            # Client hung up mid-orchestration: stop the work rather than
            # letting it run on and spend budget nobody is listening to.
            if not task.done():
                task.cancel()
            else:
                # Surface a crash that happened after the stream closed.
                exc = task.exception() if not task.cancelled() else None
                if exc:
                    logger.error("orchestration task failed: %s", exc)

    return EventSourceResponse(events())
