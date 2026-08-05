"""Grounded answer generation.

SOLUTION.md §4.4. The generation contract is closed-book: the model answers
only from the retrieved context and cites a real record ID for every factual
claim. Everything the corpus itself demands in its published §15.2
"Retrieval Grounding Rules" is encoded in the system prompt here, and then
independently *checked* in grounding_gate.py — prompt for behaviour, validate
for guarantee.

Note on temperature: SOLUTION.md specified 0.1 for determinism. gpt-5-mini
rejects any value but the default, so we cannot set it. Grounding does not
depend on it — GroundingGate is deterministic post-processing, and a
reasoning model is if anything better at faithful extraction.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Sequence

from app.chains.retrieval import RetrievedChunk
from app.core.llm import chat

logger = logging.getLogger(__name__)

INSUFFICIENT_EVIDENCE_MESSAGE = (
    "The available Pandora knowledge base does not contain sufficient "
    "evidence to answer this question."
)

CITATION_PATTERN = re.compile(r"\[([A-Z]{2,4}-[A-Z0-9]+)\]")

_SYSTEM = """You are the Pandora Knowledge Guardian. You answer questions about Pandora \
strictly from retrieved records supplied to you, for guardians responding to real incidents.

THE CONTRACT — every rule below comes from the corpus's own §15.2 "Retrieval Grounding Rules".

1. CLOSED BOOK. Answer only from the CONTEXT RECORDS below. You have no other knowledge of
   Pandora. Never import facts about Earth oceans, real marine biology, or real emergency
   protocols — the corpus is fictional and self-consistent, and outside facts are hallucinations
   even when true on Earth.

2. CITE EVERY CLAIM. End each sentence that states a fact with the ID it came from, in square
   brackets — exactly the token shown in that record's "cite as" field: [INC-005], [FAU-014],
   [WS-03], [SEC-2]. Use those tokens verbatim. Never invent an ID and never cite one that is
   not in the context below. Every bullet point under an evidence heading is a factual claim and
   must carry a marker — there are no unattributed bullets. Only a pure connective sentence
   ("Two hypotheses remain open.") may go uncited.

3. HYPOTHESES STAY HYPOTHESES. Where a record lists plausible causes, present them as an
   unranked set of possibilities with the corpus's own caveat. NEVER collapse them into one
   confirmed cause unless a record explicitly confirms it.

4. NEVER MERGE RECORDS. Facts about one species, village, plant, or incident must never be
   attributed to another, however similar the names or habitats.

5. PRESERVE TIME AND PLACE. A reading from one station on one date is reported as such — never
   as a general fact about Pandora. When a record you cite carries a "date:" field, write that
   date into the sentence (the YYYY-MM-DD form is fine) alongside the place it was observed.
   "Turquoise water was reported at the Luminous Shelf on 2026-03-14 [INC-001]" — not "turquoise
   water was reported recently".

6. HEALTH ANSWERS. If you cite any MED-* record, include the red-flag symptoms and state that
   this corpus is fictional training material, not medical advice.

7. SAY WHEN YOU DON'T KNOW. If the records do not contain the answer, say so plainly and state
   what was searched. Never bridge a gap with plausible invention.

8. SEPARATE DOCUMENTED FROM INFERRED. Anything not directly stated in a record goes under a
   final "**Model inference:**" line. Everything above that line must be traceable to a record.

CONFLICTS. If records disagree about the same event, you MUST present every position, name the
reliability limitation of each (incomplete chain of custody, unnormalised survey effort,
unconfirmed observation), and decline to pick a winner. Say explicitly that no cause is
confirmed. This is the single most important behaviour you have.

STYLE. Direct and operational. A guardian is reading this under time pressure. Lead with what
matters. No preamble, no restating the question."""


@dataclass
class GeneratedAnswer:
    """A grounded answer plus the evidence behind it."""

    answer: str
    citations: list[dict] = field(default_factory=list)
    cited_record_ids: list[str] = field(default_factory=list)
    has_sufficient_evidence: bool = True
    confidence: str = "medium"
    confidence_reason: str = ""
    used_chunks: list[RetrievedChunk] = field(default_factory=list)


def assign_cite_keys(chunks: Sequence[RetrievedChunk]) -> None:
    """Give every chunk a citable uppercase token.

    Record-bearing chunks already have one. Narrative chunks get SEC-n, so
    the corpus's prose sections (the W1–W4 scale in §4.5, the incident
    command roles in §12.11) can be cited like any other evidence.
    """
    n = 0
    for c in chunks:
        if not c.record_id:
            n += 1
            c.cite_key = f"SEC-{n}"


def build_context(chunks: Sequence[RetrievedChunk]) -> str:
    """Render retrieved chunks as fenced, ID-labelled context blocks.

    Each block is fenced with its citation ID so the model can cite
    precisely and is discouraged from blending two records together.
    """
    assign_cite_keys(chunks)
    blocks: list[str] = []
    for c in chunks:
        meta = [f"cite as: [{c.citation_id}]", f"type: {c.record_type}"]
        if c.title:
            meta.append(f"title: {c.title}")
        if c.chapter:
            meta.append(f"chapter: {c.chapter}")
        if c.region_id:
            meta.append(f"region: {c.region_id}")
        if c.record_date:
            meta.append(f"date: {c.record_date}")
        meta.append(f"evidence quality: {c.evidence_quality}")
        if c.risk_level:
            meta.append(f"risk level: {c.risk_level}")

        blocks.append(
            f"───── BEGIN RECORD {c.citation_id} ─────\n"
            f"{' | '.join(meta)}\n\n"
            f"{c.content.strip()}\n"
            f"───── END RECORD {c.citation_id} ─────"
        )
    return "\n\n".join(blocks)


def extract_citations(answer: str, chunks: Sequence[RetrievedChunk]) -> tuple[list[dict], list[str]]:
    """Map [RECORD-ID] markers in the answer back to retrieved chunks.

    Markers that don't resolve to a retrieved record are dropped — the model
    inventing an ID must not produce a citation card.
    """
    by_id: dict[str, RetrievedChunk] = {}
    for c in chunks:
        by_id.setdefault(c.citation_id, c)

    seen: list[str] = []
    for rid in CITATION_PATTERN.findall(answer):
        if rid in by_id and rid not in seen:
            seen.append(rid)

    citations = [by_id[rid].to_citation(i + 1) for i, rid in enumerate(seen)]
    return citations, seen


def _score_confidence(
    chunks: Sequence[RetrievedChunk], cited: Sequence[str], conflicted: bool
) -> tuple[str, str]:
    """Confidence with a stated reason — never a bare label."""
    if not cited:
        return "insufficient", "no retrieved record supported the answer"

    n = len(cited)
    top = max((c.normalised_score for c in chunks), default=0.0)
    disputed = sum(
        1 for c in chunks if c.citation_id in cited and c.evidence_quality == "disputed report"
    )

    if conflicted or disputed:
        return (
            "moderate",
            f"{n} sources, {disputed or 'some'} carrying disputed or unverified evidence — "
            "the records do not agree",
        )
    if n >= 3 and top >= 0.55:
        return "high", f"{n} sources, all consistent, strong retrieval match"
    if n >= 2:
        return "medium", f"{n} sources, moderate retrieval match"
    return "low", "only one supporting record was found"


def generate_answer(
    question: str,
    chunks: Sequence[RetrievedChunk],
    *,
    extra_instruction: str = "",
    max_tokens: int | None = None,
) -> GeneratedAnswer:
    """Produce a grounded, cited answer from retrieved records."""
    if not chunks:
        return GeneratedAnswer(
            answer=(
                f"{INSUFFICIENT_EVIDENCE_MESSAGE}\n\n"
                "No records in the Pandora knowledge base matched this question."
            ),
            has_sufficient_evidence=False,
            confidence="insufficient",
            confidence_reason="retrieval returned no candidates",
        )

    context = build_context(chunks)
    user = (
        f"QUESTION\n{question}\n\n"
        f"CONTEXT RECORDS\n\n{context}\n\n"
        "Answer the question using only these records. Cite every factual claim with its "
        "record ID in square brackets."
    )
    if extra_instruction:
        user += f"\n\nADDITIONAL INSTRUCTION\n{extra_instruction}"

    answer = chat(
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
        max_tokens=max_tokens,
    )

    citations, cited_ids = extract_citations(answer, chunks)

    lowered = answer.lower()
    conflicted = any(
        k in lowered
        for k in ("disagree", "conflict", "not confirmed", "no confirmed cause",
                  "chain of custody", "cannot be confirmed", "contradict")
    )
    insufficient = (
        INSUFFICIENT_EVIDENCE_MESSAGE.lower()[:60] in lowered
        or "does not contain sufficient evidence" in lowered
    )

    confidence, reason = _score_confidence(chunks, cited_ids, conflicted)
    if insufficient:
        confidence, reason = "insufficient", "the corpus does not cover this question"

    return GeneratedAnswer(
        answer=answer,
        citations=citations,
        cited_record_ids=cited_ids,
        has_sufficient_evidence=not insufficient and bool(cited_ids),
        confidence=confidence,
        confidence_reason=reason,
        used_chunks=list(chunks),
    )
