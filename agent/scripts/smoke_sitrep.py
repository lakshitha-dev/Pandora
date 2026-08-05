"""End-to-end smoke test for the agentic layer (Layer 5).

Exercises every routing mode and both degradation paths against the live
service. Run it with the agent service already up:

    uvicorn app.main:app --port 8000
    python -m scripts.smoke_sitrep

Each check prints PASS/FAIL and the evidence behind the verdict, so a
failure tells you which §5 guarantee broke rather than just that something
did. Exits non-zero if any check fails.
"""

from __future__ import annotations

import json
import os
import sys
import time

import httpx

# The Windows console defaults to cp1252, which cannot encode the box-drawing
# and emoji characters in this corpus's record titles. Without this the script
# dies on a print() after the checks have already passed — reporting a crash
# for a run that succeeded.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE = os.environ.get("AGENT_BASE_URL", "http://localhost:8000")
KEY = os.environ.get("AGENT_SERVICE_KEY", "dev-internal-key-change-me")
HEADERS = {"X-Internal-Key": KEY, "Content-Type": "application/json"}
TIMEOUT = httpx.Timeout(180.0)

TURQUOISE = (
    "The water near Awa Reef has turned turquoise and the fish are leaving the area."
)

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    if detail:
        print(f"        {detail}")
    if not ok:
        failures.append(name)


def post_sitrep(**body) -> dict:
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.post(f"{BASE}/agent/sitrep", headers=HEADERS, json=body)
        r.raise_for_status()
        return r.json()


def section(report: dict, section_type: str) -> dict:
    return next(
        (s for s in report["situation_report"]["sections"] if s["section_type"] == section_type),
        {},
    )


# ─────────────────────────────────────────────────────────────────────────


def test_health() -> bool:
    print("\n[1] Health — nothing works without an indexed corpus")
    with httpx.Client(timeout=TIMEOUT) as client:
        data = client.get(f"{BASE}/health").json()
    check("corpus indexed", data.get("corpus_indexed") is True,
          f"{data.get('corpus_chunk_count')} chunks, {data.get('corpus_record_count')} records")
    check("search reachable", data.get("search_index_reachable") is True)
    check("llm reachable", data.get("llm_reachable") is True)
    return bool(data.get("corpus_indexed"))


def test_sitrep_mode() -> None:
    print("\n[2] sitrep mode — three specialists, three sections")
    started = time.perf_counter()
    data = post_sitrep(question=TURQUOISE)
    elapsed = time.perf_counter() - started
    report = data["situation_report"]

    check("assembly_mode is sitrep", report["assembly_mode"] == "sitrep",
          f"got {report['assembly_mode']!r}")
    owners = {s["owning_agent"] for s in report["sections"] if s["status"] == "filled"}
    check("each filled section has a distinct owning agent", len(owners) >= 2,
          f"owners: {sorted(owners)}")
    check("priority carries a citation", bool(report.get("priority_citation")),
          f"{report['priority_class']} — {report.get('priority_citation')!r} p.{report.get('priority_page')}")
    check("citations resolve to record IDs", len(data["citations"]) > 0,
          f"{len(data['citations'])} sources: {[c['record_id'] for c in data['citations']][:6]}")
    check("LLM call cap respected", data["llm_call_count"] <= 8,
          f"{data['llm_call_count']} calls in {elapsed:.1f}s")
    check("regions drive the map", isinstance(report.get("affected_region_ids"), list),
          f"regions: {report.get('affected_region_ids')}")


def test_contested_state() -> None:
    """The gate that matters most — §14.3 is a planted trap with a stated
    expected answer."""
    print("\n[3] The Contested state — FN-A / FN-B / LAB-C, no cause declared")
    data = post_sitrep(question=TURQUOISE)
    causes = section(data, "likely_causes")
    content = (causes.get("content") or "").lower()
    conflict_ids = {r for c in data.get("conflicts", []) for r in c["record_ids"]}

    check("a conflict was detected", bool(data.get("conflicts")),
          f"records: {sorted(conflict_ids)}")
    check("no single cause is declared confirmed",
          any(t in content for t in ("not confirmed", "no confirmed", "not established",
                                     "cannot be confirmed", "hypothes")),
          "likely_causes must present hypotheses, never one confirmed cause")
    if data.get("conflicts"):
        c = data["conflicts"][0]
        check("every position is kept separately", len(c.get("positions", [])) >= 2,
              f"{len(c.get('positions', []))} positions, limitation: {c.get('reliability_limitation')!r}")


def test_focused_mode() -> None:
    print("\n[4] focused mode — one specialist, others not applicable")
    data = post_sitrep(question="What is the approach distance for a Deepbell Singer?")
    report = data["situation_report"]
    statuses = {s["section_type"]: s["status"] for s in report["sections"]}
    n_a = sum(1 for v in statuses.values() if v == "not_applicable")

    check("assembly_mode is focused", report["assembly_mode"] == "focused",
          f"got {report['assembly_mode']!r}")
    check("two sections are marked not applicable", n_a == 2, f"statuses: {statuses}")
    check("LLM calls stayed low", data["llm_call_count"] <= 3,
          f"{data['llm_call_count']} calls")


def test_compare_mode() -> None:
    print("\n[5] compare mode — both subjects retrieved independently")
    data = post_sitrep(
        question=(
            "Compare the recommended responses for water contamination and an "
            "underwater volcanic event."
        )
    )
    report = data["situation_report"]
    record_ids = {c["record_id"] for c in data["citations"]}

    check("assembly_mode is compare", report["assembly_mode"] == "compare",
          f"got {report['assembly_mode']!r}")
    check("neither side was starved", len(record_ids) >= 2,
          f"cited: {sorted(record_ids)[:8]}")


def test_honesty_flip() -> None:
    print("\n[6] The honesty flip — absent from the corpus")
    data = post_sitrep(question="What is the population of Tokyo?")
    check("has_sufficient_evidence is false", data["has_sufficient_evidence"] is False)
    text = data.get("insufficient_evidence") or ""
    check("the brief's mandated sentence appears verbatim",
          "does not contain sufficient evidence to answer this question" in text,
          text.splitlines()[0][:100] if text else "(empty)")


def test_stream() -> None:
    print("\n[7] SSE trace — parallel fill is visible on the wire")
    steps: list[str] = []
    body = json.dumps({"question": TURQUOISE})
    with httpx.Client(timeout=TIMEOUT) as client:
        with client.stream(
            "POST", f"{BASE}/agent/sitrep",
            headers={**HEADERS, "Accept": "text/event-stream"}, content=body,
        ) as r:
            for line in r.iter_lines():
                if line.startswith("event:"):
                    steps.append(line.split(":", 1)[1].strip())

    check("stream produced events", len(steps) > 5, f"{len(steps)} events")
    check("priority classified before generation",
          "priority.classified" in steps
          and ("section.filling" not in steps
               or steps.index("priority.classified") < steps.index("section.filling")),
          "the triage banner must render immediately")
    if "section.completed" in steps and "section.filling" in steps:
        first_done = steps.index("section.completed")
        concurrent = steps[:first_done].count("section.filling")
        check("sections fill concurrently", concurrent >= 2,
              f"{concurrent} sections started before the first completed")
    check("terminal event present",
          steps[-1] in ("answer.completed", "error"), f"last event: {steps[-1] if steps else '(none)'}")


def main() -> int:
    print(f"Smoke-testing the agentic layer at {BASE}")
    if not test_health():
        print("\nCorpus is not indexed — seed it first. Aborting.")
        return 1

    for fn in (test_sitrep_mode, test_contested_state, test_focused_mode,
               test_compare_mode, test_honesty_flip, test_stream):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            check(f"{fn.__name__} raised", False, f"{type(exc).__name__}: {exc}")

    print(f"\n{'─' * 60}")
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for f in failures:
            print(f"  · {f}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
