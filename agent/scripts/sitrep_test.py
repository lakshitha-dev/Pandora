"""Exercise POST /agent/sitrep — the Layer 5 orchestrated path.

    python scripts/sitrep_test.py                # the turquoise-water kill shot
    python scripts/sitrep_test.py --mode focused # force a routing mode
    python scripts/sitrep_test.py -q "..."       # any question

Checks the six criteria the corpus states on page 48 when the question is the
conflict one, and prints the assembled report so the trace can be eyeballed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_QUESTION = (
    "The water near Awa Reef has turned turquoise and the fish are leaving the area."
)


def read_key() -> str:
    env = Path(__file__).resolve().parents[1] / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("AGENT_SERVICE_KEY="):
                return line.split("=", 1)[1].strip()
    return "dev-internal-key-change-me"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-q", "--question", default=DEFAULT_QUESTION)
    ap.add_argument("--mode", default=None, choices=["sitrep", "focused", "compare"])
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--timeout", type=int, default=280)
    args = ap.parse_args()

    body = {"question": args.question}
    if args.mode:
        body["mode"] = args.mode

    req = urllib.request.Request(
        f"{args.url}/agent/sitrep",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Internal-Key": read_key(),
            "Accept": "application/json",
        },
    )

    print(f"question: {args.question}")
    print("dispatching...\n")
    t = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read()[:600].decode(errors='replace')}")
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"{type(e).__name__}: {e}")
        return 1
    el = time.perf_counter() - t

    sr = d["situation_report"]
    g = d["grounding"]
    rules_ok = sum(1 for x in g["rules"] if x["passed"])

    print(f"LATENCY     {el:.1f}s   llm_calls={d['llm_call_count']}   partial={sr['was_partial']}")
    print(f"ASSEMBLY    {sr['assembly_mode']}")
    print(f"PRIORITY    {sr['priority_class']} ({sr['priority_label']})")
    print(f"            {sr['priority_reason'][:120]}")
    print(f"            cite={sr['priority_citation']!r} page={sr['priority_page']}")
    print(f"REGIONS     {sr['affected_region_ids']}")
    print(f"CONFIDENCE  {sr['confidence_level']} :: {sr['confidence_reason']}")
    print(f"GROUNDING   {g['groundedness']}%   rules {rules_ok}/{len(g['rules'])}")
    print(f"SUFFICIENT  {d['has_sufficient_evidence']}")
    print(f"CITATIONS   {[c['record_id'] for c in d['citations']]}")

    print("\nSECTIONS")
    for s in sr["sections"]:
        print(
            f"  [{s['status']:15}] {s['section_type']:20} "
            f"agent={s['owning_agent']:22} "
            f"claims={s['supported_claim_count']}/{s['claim_count']} {s['duration_ms']}ms"
        )
        if s.get("empty_reason"):
            print(f"      reason: {s['empty_reason'][:110]}")

    print("\nRULES")
    for x in g["rules"]:
        print(f"  [{'PASS' if x['passed'] else 'FAIL'}] {x['number']}. {x['name']}")
        print(f"         {x['detail'][:110]}")

    print("\nCONFLICTS")
    if not d["conflicts"]:
        print("  (none)")
    for c in d["conflicts"]:
        print(f"  {c['record_ids']}")
        print(f"    {c['reliability_limitation']}")

    for s in sr["sections"]:
        if s["section_type"] == "likely_causes" and s["content"]:
            print("\n--- likely_causes ---")
            print(s["content"][:1500])

    # Kill-shot criteria (corpus p.48) — only meaningful on the conflict question.
    text = " ".join(s["content"] for s in sr["sections"]).lower()
    if "turquoise" in args.question.lower() or "awa reef" in args.question.lower():
        checks = [
            ("presents FN-A", "fn-a" in text),
            ("presents FN-B", "fn-b" in text),
            ("presents LAB-C", "lab-c" in text),
            ("flags chain of custody", "chain of custody" in text or "chain-of-custody" in text),
            ("no confirmed cause", any(k in text for k in (
                "not confirmed", "no confirmed", "cannot be confirmed",
                "remain possible", "not established"))),
            ("recommends sampling", "sampl" in text),
        ]
        print("\nKILL-SHOT CRITERIA (corpus p.48)")
        met = 0
        for name, ok in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
            met += ok
        print(f"\n  {met}/6")
        return 0 if met == 6 else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
