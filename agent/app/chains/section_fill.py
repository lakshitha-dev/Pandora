"""Shared section-fill logic — used by /rag/query AND the specialist agents.

Extracted so the orchestrator's specialists (app/agents/specialists.py) call
the exact same retrieve → generate → GroundingGate pipeline that /rag/query
uses directly. Two callers, one implementation — no risk of the agentic
layer drifting from the plain-query behaviour that Layer 1 verified.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.chains.generation import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    GeneratedAnswer,
    generate_answer,
)
from app.chains.grounding_gate import GateResult, run_gate
from app.chains.retrieval import RetrievedChunk, corpus_covers, retrieve
from app.core.config import get_settings
from app.core.llm import LLMError
from app.models.schemas import QueryRequest, ReportSection, SectionStatus, SectionType

logger = logging.getLogger(__name__)

# Section-specific retrieval filters and instructions. One profile per
# content section lets a single fill function serve any of the three
# specialist-owned sections (SOLUTION.md §5.3) or a plain unfiltered answer.
SECTION_PROFILES: dict[SectionType, dict] = {
    SectionType.AFFECTED_SPECIES: {
        "record_types": ["fauna", "flora", "policy", "region"],
        "instruction": (
            "List the species this situation puts at risk. For each: its record ID, habitat, "
            "the documented pressures relevant to THIS event, and the protection guidance. "
            "Assemble each species from its own record only — never generalise one species' "
            "pressures to another. If no species record matches, say so plainly."
        ),
    },
    SectionType.LIKELY_CAUSES: {
        "record_types": ["incident", "monitoring", "field_note", "region", "narrative"],
        "instruction": (
            "State what may have caused this, as an UNRANKED set of hypotheses with the "
            "evidence for each. Separate what the records establish from what they do not. "
            "If records conflict, present every position with its reliability limitation and "
            "state explicitly that no cause is confirmed. Never name a confirmed cause unless "
            "a record confirms it."
        ),
    },
    SectionType.RECOMMENDED_ACTIONS: {
        "record_types": ["incident", "knowledge_card", "health", "settlement", "policy", "narrative"],
        "instruction": (
            "Give the ordered, executable actions a response team should take now, each cited. "
            "Include responder safety, the incident command roles to activate, and the minimum "
            "incident dataset to record. Where the corpus provides a public communication "
            "template, fill it in."
        ),
    },
}

CONTENT_SECTIONS = [
    SectionType.AFFECTED_SPECIES,
    SectionType.LIKELY_CAUSES,
    SectionType.RECOMMENDED_ACTIONS,
]

# Below this groundedness, an answer carrying resolving citations is assumed to
# have put them in the wrong place rather than to be ungrounded. Sits well under
# the observed good-run floor (~86%) and well over the bad-run value (0%), which
# the measured bimodality makes an easy line to draw.
CITATION_REPAIR_THRESHOLD = 50

CITATION_REPAIR_INSTRUCTION = (
    "CITATION PLACEMENT — your previous attempt collected its record IDs into a list "
    "instead of attaching them to the claims they support. Put the marker at the END OF "
    "EVERY SENTENCE that states a fact, inline, like this: 'Restrict shellfish harvest "
    "and set an exclusion boundary [INC-001].' Do NOT write a Sources, References, or "
    "Records Used section — the interface builds that from your inline markers. A "
    "sentence with no marker is dropped as unsupported."
)

PLAIN_ANSWER_INSTRUCTION = (
    "Answer the question directly and completely from the records. Lead with the answer, "
    "not a restatement of the question. Cite every factual claim."
)

# Question vocabulary → record types, for the plain (unfiltered) Layer 1 path.
#
# Measured, not guessed: "which marine species are most vulnerable to water
# contamination?" returns almost all *narrative* prose unfiltered, because the
# corpus's chapter intros use that vocabulary far more densely than any single
# FAU-* record does. Hybrid search is doing its job — the prose really is the
# best lexical and semantic match — but the useful answer lives in the records.
# One metadata filter took that question's top-6 from 0/6 to 6/6 relevant.
#
# Deliberately a keyword map and not an LLM call: it is free, deterministic,
# adds no latency to the 45-mark core, and cannot fail at demo time. It is only
# a *hint* — fill_section widens straight back out if the narrowed pass starves,
# so a wrong guess costs one extra search, never an answer.
_TYPE_HINTS: tuple[tuple[tuple[str, ...], list[str]], ...] = (
    (("species", "creature", "animal", "fauna", "wildlife", "fish", "bird", "plant",
      "flora", "coral", "habitat", "vulnerable", "endangered"),
     ["fauna", "flora", "region", "policy"]),
    (("symptom", "sick", "illness", "injur", "treat", "first aid", "poison",
      "sting", "exposure", "medical", "health"),
     ["health", "knowledge_card", "incident"]),
    (("village", "settlement", "community", "clan", "population", "resident"),
     ["settlement", "region", "policy"]),
    (("rule", "policy", "regulation", "permit", "protocol", "law", "prohibited",
      "allowed", "authoris", "authoriz"),
     ["policy", "knowledge_card"]),
    (("reading", "measurement", "station", "survey", "sensor", "sample",
      "turbidity", "salinity", "ph "),
     ["monitoring", "field_note", "incident"]),
    (("incident", "spill", "contamination", "damage", "stranding", "response",
      "emergency", "evacuat", "what should", "what actions", "immediate action"),
     ["incident", "knowledge_card", "policy", "field_note"]),
)


def infer_record_types(question: str) -> list[str] | None:
    """Guess which record types a plain question is really asking about.

    Returns None when nothing matches, which leaves retrieval unfiltered —
    the previous behaviour. Multiple matching groups are unioned rather than
    fought over, since a widened filter still beats no filter.
    """
    lowered = question.lower()
    hit: list[str] = []
    for triggers, types in _TYPE_HINTS:
        if any(t in lowered for t in triggers):
            hit.extend(t for t in types if t not in hit)
    return hit or None


@dataclass
class SectionFillResult:
    section: ReportSection
    chunks: list[RetrievedChunk]
    answer: GeneratedAnswer | None
    gate: GateResult | None


def rewrite_with_history(question: str, history) -> str:
    """Cheap last-turn coreference: prepend the prior user turn as context."""
    if not history:
        return question
    prior = next((t.content for t in reversed(history) if t.role == "user"), None)
    if not prior or len(question) > 120:
        return question
    return f"{prior} {question}"


def fill_section(
    section: SectionType | None,
    question: str,
    *,
    req: QueryRequest | None = None,
    record_type_filter: list[str] | None = None,
    region_id_filter: list[str] | None = None,
    top_k: int | None = None,
    owning_agent: str = "single_agent",
) -> SectionFillResult:
    """Retrieve and generate one report section, or a plain grounded answer.

    `section=None` is the Layer 1 path: unfiltered retrieval, no
    section-specific framing. Callable either with a QueryRequest (the
    /rag/query router) or with plain kwargs (a specialist agent, which has
    no QueryRequest of its own).
    """
    started = time.perf_counter()
    settings = get_settings()

    record_type_filter = record_type_filter or (req.record_type_filter if req else None)
    region_id_filter = region_id_filter or (req.region_id_filter if req else None)
    top_k = top_k or (req.top_k if req else None) or settings.retrieval_top_k

    # The relevance floor runs before retrieval and before any LLM call, so an
    # out-of-corpus question costs one embedding rather than a generation. It
    # guards the *whole* question, so it is checked once on the Layer 1 path
    # (section=None) and once by the orchestrator before it dispatches — never
    # per-section, which would let two specialists refuse while a third answers.
    if section is None:
        covered, similarity = corpus_covers(question)
        if not covered:
            return SectionFillResult(
                section=ReportSection(
                    section_type=SectionType.LIKELY_CAUSES,
                    status=SectionStatus.EMPTY,
                    empty_reason="the corpus does not cover this question",
                    content=(
                        f"{INSUFFICIENT_EVIDENCE_MESSAGE}\n\n"
                        "The Pandora knowledge base was searched and no record was a close "
                        "enough match to ground an answer. Nothing here is inferred from "
                        "outside the corpus."
                    ),
                    owning_agent=owning_agent,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                ),
                chunks=[],
                answer=GeneratedAnswer(
                    answer=INSUFFICIENT_EVIDENCE_MESSAGE,
                    has_sufficient_evidence=False,
                    confidence="insufficient",
                    confidence_reason=(
                        f"no record cleared the relevance floor (best match {similarity:.2f})"
                    ),
                ),
                gate=None,
            )

    profile = SECTION_PROFILES.get(section) if section else None
    instruction = profile["instruction"] if profile else PLAIN_ANSWER_INSTRUCTION
    record_types = record_type_filter or (
        profile["record_types"] if profile else infer_record_types(question)
    )
    out_section = section or SectionType.LIKELY_CAUSES

    chunks = retrieve(
        question, top_k=top_k, record_types=record_types, region_ids=region_id_filter
    )

    # A section's record-type filter is tuned for incident-shaped questions.
    # A general question ("what traditional practices support conservation?")
    # can fall outside it and starve — POL-005 answers that question but the
    # likely_causes filter excludes policy records. When the filtered pass
    # surfaces almost no record-bearing evidence, widen rather than fail.
    record_bearing = sum(1 for c in chunks if c.record_id)
    if record_types and record_bearing < 2:
        widened = retrieve(question, top_k=top_k, region_ids=region_id_filter)
        if sum(1 for c in widened if c.record_id) > record_bearing:
            logger.info("widening retrieval past the %s type filter", out_section.value)
            chunks = widened

    if not chunks:
        return SectionFillResult(
            section=ReportSection(
                section_type=out_section, status=SectionStatus.EMPTY,
                empty_reason="no records matched this question",
                owning_agent=owning_agent,
                duration_ms=int((time.perf_counter() - started) * 1000),
            ),
            chunks=[], answer=None, gate=None,
        )

    # One retry, hard-capped by a counter (SOLUTION.md §5.5) — never a loop.
    # A reasoning model spends a variable share of its budget on reasoning, so
    # an occasional finish_reason='length' with empty content is expected
    # rather than exceptional. Retry once with a larger budget.
    result: GeneratedAnswer | None = None
    attempts = 0
    last_error: LLMError | None = None
    while attempts <= settings.max_retries:
        try:
            result = generate_answer(
                question,
                chunks,
                extra_instruction=instruction,
                max_tokens=settings.chat_max_completion_tokens * (2 if attempts else 1),
            )
            break
        except LLMError as exc:
            last_error = exc
            attempts += 1
            logger.warning("section %s attempt %d failed: %s", out_section.value, attempts, exc)

    if result is None:
        raise last_error or LLMError("generation failed")

    gate = run_gate(
        result.answer, chunks, has_sufficient_evidence=result.has_sufficient_evidence
    )

    # Citation-format repair, one attempt, counter-capped like every other
    # retry here.
    #
    # `gpt-5-mini` rejects any temperature but its default, so generation is
    # non-deterministic and we cannot turn that off. Measured over three trials
    # per question (scripts/measure_citation_variance.py), inline-citation
    # compliance came out **bimodal — 0% or ~100%, never in between**: the model
    # either marks every sentence or collects all its markers into a trailing
    # sources block. The evidence is correctly retrieved and correctly cited
    # either way, but corpus §15.2.1 requires the attribution to be *per claim*,
    # so the trailing-block form genuinely fails the rule rather than merely
    # looking different. Prompt wording alone did not make this reliable.
    #
    # Because the failure is bimodal, it is cheap to detect and worth one
    # retargeted retry: a near-zero score alongside markers that *do* resolve
    # means the model had the right evidence and only misplaced it.
    # The trigger deliberately does NOT require markers to already be present.
    # An answer with no markers at all is the same formatting failure in its
    # extreme form — the records were retrieved and the relevance floor already
    # cleared them, so the evidence is there and only the attribution is missing.
    if attempts < settings.max_retries and gate.groundedness < CITATION_REPAIR_THRESHOLD:
        logger.info(
            "section %s scored %d%% with %d resolving citations — retrying for inline form",
            out_section.value, gate.groundedness, len(result.cited_record_ids),
        )
        try:
            repaired = generate_answer(
                question,
                chunks,
                extra_instruction=f"{instruction}\n\n{CITATION_REPAIR_INSTRUCTION}",
                max_tokens=settings.chat_max_completion_tokens,
            )
            repaired_gate = run_gate(
                repaired.answer, chunks,
                has_sufficient_evidence=repaired.has_sufficient_evidence,
            )
            # Keep the better answer, never blindly the newer one.
            if repaired_gate.groundedness > gate.groundedness:
                result, gate = repaired, repaired_gate
        except LLMError as exc:
            logger.warning("citation repair failed, keeping original: %s", exc)

    return SectionFillResult(
        section=ReportSection(
            section_type=out_section,
            status=SectionStatus.FILLED if result.has_sufficient_evidence else SectionStatus.EMPTY,
            empty_reason=None if result.has_sufficient_evidence else "insufficient evidence in the corpus",
            content=result.answer,
            claim_count=gate.claim_count,
            supported_claim_count=gate.supported_claim_count,
            owning_agent=owning_agent,
            duration_ms=int((time.perf_counter() - started) * 1000),
        ),
        chunks=chunks, answer=result, gate=gate,
    )
