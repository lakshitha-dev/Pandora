"""The hard limits — SOLUTION.md §5.5.

"Unbounded agent loops are the single most common way a hackathon demo dies
on stage." These caps are enforced by counters in orchestrator state, not by
prompt instruction, and these tests are what says so.
"""

from __future__ import annotations

import threading
import time

from app.agents.budget import Budget
from app.core.config import get_settings


def make_budget(**kwargs) -> Budget:
    defaults = {
        "deadline": time.perf_counter() + 45,
        "max_llm_calls": 8,
        "max_retries": 1,
    }
    defaults.update(kwargs)
    return Budget(**defaults)


def test_llm_calls_are_capped_at_eight():
    budget = make_budget()
    assert all(budget.spend_llm_call() for _ in range(8))
    assert not budget.spend_llm_call(), "the 9th LLM call must be refused"
    assert budget.llm_calls == 8


def test_retry_is_capped_at_one():
    budget = make_budget()
    assert budget.spend_retry()
    assert not budget.spend_retry(), "a second retry must be refused — never a loop"
    assert budget.retries_used == 1


def test_the_retry_cap_is_global_across_specialists():
    """Three specialists share one budget. A per-specialist retry counter
    would allow three retries per query and blow the latency ceiling."""
    budget = make_budget()
    granted = [budget.spend_retry() for _ in range(3)]
    assert granted == [True, False, False]


def test_expired_budget_reports_no_remaining_time():
    budget = make_budget(deadline=time.perf_counter() - 1)
    assert budget.expired
    assert budget.remaining_seconds == 0.0


def test_counters_hold_under_concurrent_specialists():
    """Specialists run in worker threads and all charge the same budget, so
    every mutation takes a lock. Without it the cap leaks."""
    budget = make_budget(max_llm_calls=50)
    granted: list[bool] = []
    lock = threading.Lock()

    def worker() -> None:
        for _ in range(20):
            ok = budget.spend_llm_call()
            with lock:
                granted.append(ok)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(granted) == 50, "exactly the cap must be granted, no more"
    assert budget.llm_calls == 50


def test_budget_starts_from_settings():
    budget = Budget.start(get_settings())
    settings = get_settings()
    assert budget.max_llm_calls == settings.max_llm_calls_per_query
    assert budget.max_retries == settings.max_retries
    assert budget.remaining_seconds <= settings.orchestration_budget_seconds
