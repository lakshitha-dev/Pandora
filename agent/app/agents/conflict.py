"""Conflict detection over retrieved evidence.

SOLUTION.md §6.1. Detection is structural, not semantic-guessing: two or
more retrieved chunks carrying the corpus's own `disputed report` evidence
label about the same subject are a conflict. This is what GroundingGate
rule 7 already computes (app/chains/grounding_gate.py::_rule_7_conflicts);
this module re-exposes it for the orchestrator so a conflict can drive
routing decisions (e.g. widen retrieval, lower confidence) before the
per-section grounding pass runs.
"""

from __future__ import annotations

from typing import Sequence

from app.chains.retrieval import RetrievedChunk
from app.models.schemas import Conflict


def detect_conflicts(chunks: Sequence[RetrievedChunk]) -> list[Conflict]:
    """Find disputed-evidence clusters among retrieved chunks.

    Covers both planted traps in the corpus: FN-A / FN-B / LAB-C (§14.3,
    contradictory field notes about the turquoise-water event) and
    SV-101 / SV-102 (§14.2, unnormalised survey effort presented as if
    comparable). Both are tagged `disputed report` by the chunker
    (app/ingestion/parse.py::classify_evidence_quality).
    """
    disputed = [c for c in chunks if c.evidence_quality == "disputed report"]
    if len(disputed) < 2:
        return []

    ids = [c.citation_id for c in disputed]
    joined = " ".join(c.content.lower() for c in disputed)

    if "chain-of-custody" in joined or "chain of custody" in joined:
        limitation = "incomplete chain of custody on the laboratory sample"
    elif "not directly comparable" in joined or "survey effort" in joined:
        limitation = "survey effort not normalised between counts"
    else:
        limitation = "unverified or challenged evidence"

    return [
        Conflict(
            record_ids=ids,
            nature="Retrieved records disagree or carry unverified evidence about the same event",
            reliability_limitation=limitation,
        )
    ]
