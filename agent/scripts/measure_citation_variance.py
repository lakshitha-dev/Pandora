"""Measure run-to-run variance in inline-citation compliance.

`gpt-5-mini` is a reasoning model and rejects any temperature but its default,
so generation is non-deterministic and we cannot turn that off. The Layer 1
gate saw two questions score 0% groundedness on one run and 100% on the next
with no code change between them — the model sometimes puts its citations in a
trailing sources list instead of inline on each sentence, and GroundingGate
correctly scores that as unsupported.

A single gate run therefore cannot tell a real regression from a sample. This
measures the distribution so the pass bar is set on evidence.

    python -m scripts.measure_citation_variance [trials]
"""

from __future__ import annotations

import statistics
import sys

from app.chains.section_fill import fill_section

QUESTIONS = [
    "Which areas should receive emergency attention first, based on recent incidents?",
    "What are the immediate steps when water changes color near Awa Reef?",
    "What immediate actions should guardians take after detecting coral damage?",
]


def main() -> None:
    trials = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    print(f"{trials} trials per question. Non-determinism is the thing being measured.\n")

    worst = 100
    for q in QUESTIONS:
        scores: list[int] = []
        for _ in range(trials):
            try:
                r = fill_section(None, q, owning_agent="variance")
                scores.append(r.gate.groundedness if r.gate else 0)
            except Exception as exc:  # noqa: BLE001 - a failed trial is a data point
                print(f"    trial failed: {exc}")
                scores.append(0)
        worst = min(worst, min(scores))
        spread = max(scores) - min(scores)
        flag = "  <-- UNSTABLE" if spread >= 25 else ""
        print(f"  {[f'{s}%' for s in scores]}  min={min(scores)}%  "
              f"mean={statistics.mean(scores):.0f}%  spread={spread}{flag}")
        print(f"     {q[:72]}\n")

    print("=" * 70)
    print(f"  worst single observation across all trials: {worst}%")
    if worst < 70:
        print("  Inline-citation compliance is NOT reliable on prompt alone.")
    else:
        print("  Compliance held across every trial.")


if __name__ == "__main__":
    main()
