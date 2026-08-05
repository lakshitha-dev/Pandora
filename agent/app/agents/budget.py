"""Hard limits for one orchestration, held as counters.

SOLUTION.md §5.5 is emphatic: unbounded agent loops are the single most
common way a hackathon demo dies on stage. So the caps live here, in
orchestrator state, and are **enforced by counters — never by a prompt
instruction**. A model can ignore "only retry once"; a counter cannot.

Specialists run concurrently in worker threads and all charge the same
budget, so every mutation takes a lock.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from app.core.config import Settings


@dataclass
class Budget:
    """Wall-clock deadline plus the LLM-call and retry counters."""

    deadline: float
    max_llm_calls: int
    max_retries: int
    llm_calls: int = 0
    retries_used: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def start(cls, settings: Settings) -> "Budget":
        return cls(
            deadline=time.perf_counter() + settings.orchestration_budget_seconds,
            max_llm_calls=settings.max_llm_calls_per_query,
            max_retries=settings.max_retries,
        )

    @property
    def remaining_seconds(self) -> float:
        """Seconds left before the orchestrator must return best-available."""
        return max(0.0, self.deadline - time.perf_counter())

    @property
    def expired(self) -> bool:
        return self.remaining_seconds <= 0.0

    def spend_llm_call(self) -> bool:
        """Charge one chat completion. False means the cap is reached.

        Embeddings are not charged — the §5.5 cap counts generation calls,
        and retrieval needs its query vector regardless of the agent path.
        """
        with self._lock:
            if self.llm_calls >= self.max_llm_calls:
                return False
            self.llm_calls += 1
            return True

    def spend_retry(self) -> bool:
        """Charge the one permitted retry, globally across all specialists."""
        with self._lock:
            if self.retries_used >= self.max_retries:
                return False
            self.retries_used += 1
            return True
