"""The orchestration trace — SOLUTION.md §7, docs/API_CONTRACT.md §1.2.

Agentic architecture is invisible. A judge sees a text box and an answer,
identical to every other team's. This module is what makes the architecture
*perceivable*: every orchestration step is emitted the moment it happens, and
the browser renders three specialist orbs igniting at once.

Two properties matter more than the code:

  · **Additive only.** A step type is never removed or renamed. Three people
    build against this schema simultaneously, and an unknown step_type must
    be ignored by the client rather than crash it.

  · **Thread-safe emission.** Layers 1-4 are synchronous — the Azure Search
    and OpenAI clients block — so specialists run in worker threads via
    asyncio.to_thread and emit from *off* the event loop. asyncio.Queue is
    not thread-safe, so cross-thread emits are marshalled back onto the loop
    with call_soon_threadsafe. Without that, the events a specialist emits
    mid-flight would race with the ones the orchestrator emits.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator

from app.models.schemas import TraceEvent

logger = logging.getLogger(__name__)

# The step types in docs/API_CONTRACT.md §1.2. Listed as constants so a typo
# in a step name is a NameError at import rather than an event the frontend
# silently ignores at runtime.
QUERY_RECEIVED = "query.received"
QUERY_REWRITTEN = "query.rewritten"
QUERY_CLASSIFIED = "query.classified"
PRIORITY_CLASSIFIED = "priority.classified"
MAP_ZONE_LIT = "map.zone_lit"
ROUTE_DECIDED = "route.decided"
RETRIEVAL_STARTED = "retrieval.started"
RETRIEVAL_COMPLETED = "retrieval.completed"
AGENT_THINKING = "agent.thinking"
SECTION_FILLING = "section.filling"
SECTION_COMPLETED = "section.completed"
SECTION_UNAVAILABLE = "section.unavailable"
AGENT_COMPLETED = "agent.completed"
AGENT_TIMED_OUT = "agent.timed_out"
CONFLICT_DETECTED = "conflict.detected"
VALIDATION_RUNNING = "validation.running"
VALIDATION_RESULT = "validation.result"
SYNTHESIS_STARTED = "synthesis.started"
ANSWER_STREAMING = "answer.streaming"
ANSWER_COMPLETED = "answer.completed"
ERROR = "error"

# Terminal events. The client stops listening after either.
TERMINAL = (ANSWER_COMPLETED, ERROR)


class TraceEmitter:
    """Collects orchestration steps and streams them as they happen.

    A JSON-mode request builds one of these and simply never drains it, so
    the orchestrator has exactly one code path regardless of Accept header.
    `events` always holds the full ordered trace, which is what the gateway
    persists for replay (SOLUTION.md §9.3).
    """

    def __init__(self) -> None:
        self._sequence = 0
        self._started = time.perf_counter()
        self._queue: asyncio.Queue[TraceEvent | None] = asyncio.Queue()
        self._closed = False
        self.events: list[TraceEvent] = []
        try:
            self._loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            # Constructed outside a loop (unit tests). Cross-thread emits are
            # then impossible anyway, so the queue is never contended.
            self._loop = None

    @property
    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self._started) * 1000)

    def emit(self, step_type: str, **payload: Any) -> TraceEvent:
        """Record one step. Safe to call from any thread."""
        self._sequence += 1
        event = TraceEvent(
            step_type=step_type,
            sequence_number=self._sequence,
            duration_ms=self.elapsed_ms,
            payload=payload,
        )
        self.events.append(event)
        logger.debug("trace %d %s %s", event.sequence_number, step_type, payload)
        self._put(event)
        return event

    def close(self) -> None:
        """Signal end of stream. Idempotent."""
        if not self._closed:
            self._closed = True
            self._put(None)

    def _put(self, item: TraceEvent | None) -> None:
        if self._loop is None:
            self._queue.put_nowait(item)
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._loop:
            self._queue.put_nowait(item)
        else:
            # Emitted from a specialist's worker thread. Hop back onto the
            # loop rather than touching the queue directly.
            self._loop.call_soon_threadsafe(self._queue.put_nowait, item)

    async def stream(self) -> AsyncIterator[dict[str, str]]:
        """Yield sse-starlette frames until the emitter is closed."""
        while True:
            event = await self._queue.get()
            if event is None:
                return
            yield {"event": event.step_type, "data": event.model_dump_json()}
