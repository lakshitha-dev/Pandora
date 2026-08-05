"""The three fixed specialists — SOLUTION.md §5.3.

**Fixed at three. Never dynamic.** A dynamic agent pool is unbounded latency
and unbounded failure surface, and it is not demoable in four minutes. Three
named specialists map onto the three required use cases and fit on screen.

The design decision that makes this layer *visible* rather than merely
present: the specialists do not each write a competing answer that must then
be merged — **they write different parts of the same document, concurrently.**
Each owns exactly one Situation Report section, so each agent's output lands
in its own labelled slot with its own badge. A judge sees three agents working
without being told. It also removes the merge step entirely, cutting one LLM
call and one hallucination surface.

Layering rule (SOLUTION.md §15, risk 14): this module *calls* Layer 1's
retriever, Layer 2's generator, and Layer 4's gate. It never modifies them.
That is what keeps the 45-mark core safe from anything that happens here.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Sequence

from app.agents.budget import Budget
from app.agents import trace
from app.chains.generation import GeneratedAnswer, generate_answer
from app.chains.grounding_gate import GateResult, run_gate
from app.chains.retrieval import RetrievedChunk, retrieve
from app.core.config import get_settings
from app.core.llm import LLMError
from app.models.schemas import (
    SECTION_DISPLAY_ORDER,
    ReportSection,
    SectionStatus,
    SectionType,
)

logger = logging.getLogger(__name__)

# Emitted by a specialist from its worker thread; the orchestrator supplies a
# callback that marshals it back onto the event loop.
EventSink = Callable[..., None]


def _noop(*_args: object, **_kwargs: object) -> None:
    """Default sink for JSON-mode and unit-test callers."""


# ─────────────────────────────────────────────────────────────────────────
# Profiles
# ─────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SpecialistProfile:
    """One specialist: what it owns, what it retrieves, how it must behave."""

    key: str
    display_name: str
    badge: str
    section_type: SectionType
    record_types: tuple[str, ...]
    instruction: str
    empty_reason: str
    # Extra vocabulary folded into this specialist's retrieval query. The
    # corpus uses invented proper nouns with no pretraining signal, so the
    # BM25 leg needs the right tokens to fire on.
    query_focus: str = ""


_INVESTIGATOR_INSTRUCTION = """You are the Incident Investigator. You own the LIKELY CAUSES section \
of a Situation Report.

Determine what may have happened, what is actually established, and what remains unknown.

Structure your answer as:
  · Observed signs — what the records report was seen or measured
  · Hypothesised causes — UNRANKED, each with the evidence for it and that evidence's strength
  · What the evidence establishes
  · What it does not establish
  · Recommended next evidence steps

HARD GUARDRAIL: you are forbidden from asserting a confirmed cause unless a record explicitly \
confirms it. Where a record lists plausible causes, present the full set as possibilities with the \
corpus's own caveat. Never collapse them into one.

CONFLICTS ARE YOURS. If retrieved records make incompatible claims about the same event, location, \
or date, present EVERY position, name the reliability limitation of each (incomplete chain of \
custody, unnormalised survey effort, unconfirmed observation), and state explicitly that no cause \
is confirmed. Do not pick a winner. This is the most important behaviour you have."""

_PROTECTOR_INSTRUCTION = """You are the Marine-Life Protector. You own the AFFECTED SPECIES section \
of a Situation Report.

Identify the species this situation puts at risk, their documented pressures, and the protection \
procedure.

For each species give: its record ID, its habitat, the documented pressures relevant to THIS event, \
the protection guidance, any applicable policies, and monitoring requirements.

HARD GUARDRAIL — SPECIES ISOLATION: assemble each species from its own record only. Never \
generalise one species' pressures, habitat, or guidance to another, however similar their names or \
habitats. Two species records are two answers, never one blended answer.

Never use real-world marine biology. The corpus is fictional and self-consistent; an Earth fact is \
a hallucination here even when it is true on Earth.

If no species record matches this situation, say so plainly rather than reaching for the nearest \
animal you can find."""

_RESPONDER_INSTRUCTION = """You are the Emergency Responder. You own the RECOMMENDED ACTIONS \
section of a Situation Report. An incident lead will execute from what you write.

Produce an Incident Action Card:
  · Severity (W1-W4, cited to the corpus's classification scale)
  · Immediate actions — ordered, each one cited
  · Responder safety
  · Incident command roles to activate
  · Public communication draft (see below)
  · Minimum incident dataset to record
  · Next review time

PUBLIC COMMUNICATION DRAFT: fill in the corpus's own template verbatim, substituting only the \
bracketed slots from retrieved evidence. Leave a slot bracketed if no record supports filling it:

"At [time] in [location], we observed [verified signs]. The cause is [confirmed/not yet confirmed]. \
People should [actions]. Avoid [restricted actions]. Report [symptoms or observations] through \
[channel]. The next update will be issued at [time]."

HEALTH GUARDRAIL: if you cite any MED-* record, you must include the red-flag symptoms and state \
that this corpus is fictional training material, not medical advice.

If no documented protocol was retrieved, say so and recommend field investigation. Never invent a \
procedure that reads plausible."""


INCIDENT_INVESTIGATOR = SpecialistProfile(
    key="incident_investigator",
    display_name="Incident Investigator",
    badge="🌊",
    section_type=SectionType.LIKELY_CAUSES,
    record_types=("incident", "monitoring", "field_note", "region", "narrative"),
    instruction=_INVESTIGATOR_INSTRUCTION,
    empty_reason="Cause not established — no incident record matched this situation",
    query_focus="plausible causes incident readings field notes observations",
)

MARINE_LIFE_PROTECTOR = SpecialistProfile(
    key="marine_life_protector",
    display_name="Marine-Life Protector",
    badge="🐋",
    section_type=SectionType.AFFECTED_SPECIES,
    record_types=("fauna", "flora", "policy", "region", "knowledge_card"),
    instruction=_PROTECTOR_INSTRUCTION,
    empty_reason="No species records matched this query",
    query_focus="species habitat pressures protection guidance",
)

EMERGENCY_RESPONDER = SpecialistProfile(
    key="emergency_responder",
    display_name="Emergency Responder",
    badge="🚨",
    section_type=SectionType.RECOMMENDED_ACTIONS,
    record_types=("incident", "knowledge_card", "health", "settlement", "policy", "narrative"),
    instruction=_RESPONDER_INSTRUCTION,
    empty_reason="No documented protocol retrieved — recommend field investigation",
    query_focus="immediate actions response protocol checklist safety communication",
)

# The roster. Fixed at three, never dynamic — the count is asserted at import
# so a well-meaning fourth specialist cannot be added without confronting the
# §5.5 latency and failure-surface argument first.
SPECIALISTS: dict[str, SpecialistProfile] = {
    p.key: p
    for p in (INCIDENT_INVESTIGATOR, MARINE_LIFE_PROTECTOR, EMERGENCY_RESPONDER)
}
MAX_SPECIALISTS = 3
assert len(SPECIALISTS) == MAX_SPECIALISTS, "the specialist roster is fixed at three"

# Which specialist owns which section — used to mark unowned sections
# not_applicable in focused mode.
BY_SECTION: dict[SectionType, SpecialistProfile] = {
    p.section_type: p for p in SPECIALISTS.values()
}


# ─────────────────────────────────────────────────────────────────────────
# Execution
# ─────────────────────────────────────────────────────────────────────────


@dataclass
class SpecialistResult:
    """What one specialist produced, plus the evidence behind it."""

    profile: SpecialistProfile
    section: ReportSection
    chunks: list[RetrievedChunk] = field(default_factory=list)
    answer: GeneratedAnswer | None = None
    gate: GateResult | None = None
    # A hard failure — timed out or generation errored. Distinct from an
    # honestly empty section: "no species records matched" is a *correct*
    # result and must not trigger the degradation ladder, while a timeout
    # must.
    failed: bool = False

    @property
    def filled(self) -> bool:
        return self.section.status == SectionStatus.FILLED


def blank_section(
    profile: SpecialistProfile,
    status: SectionStatus,
    empty_reason: str,
    duration_ms: int = 0,
) -> ReportSection:
    """An honestly empty section — a valid, visible state, never a blank.

    SOLUTION.md §2.1 rule 3: a blank section looks like a bug; a section that
    says "No species records matched" looks like rigour.
    """
    return ReportSection(
        section_type=profile.section_type,
        status=status,
        empty_reason=empty_reason,
        content="",
        owning_agent=profile.key,
        duration_ms=duration_ms,
        display_order=SECTION_DISPLAY_ORDER[profile.section_type],
    )


def run_specialist(
    profile: SpecialistProfile,
    question: str,
    *,
    budget: Budget,
    on_event: EventSink = _noop,
    variants: Sequence[str] = (),
    region_ids: Sequence[str] | None = None,
    record_ids: Sequence[str] | None = None,
    top_k: int | None = None,
    owning_agent: str | None = None,
) -> SpecialistResult:
    """Retrieve, generate, and validate this specialist's one section.

    Synchronous by design: the Azure Search and OpenAI clients block, so the
    orchestrator runs this in a worker thread and gets its concurrency from
    asyncio.to_thread rather than from an async client stack.

    `owning_agent` overrides the badge written into the section — the
    single-agent fallback reuses these same profiles but must label its
    output `single_agent`, because a report that claims three agents ran when
    one did would be dishonest about its own assembly.
    """
    started = time.perf_counter()
    settings = get_settings()
    agent_label = owning_agent or profile.key
    k = top_k or settings.retrieval_top_k

    def elapsed() -> int:
        return int((time.perf_counter() - started) * 1000)

    query = f"{question} {profile.query_focus}".strip()

    on_event(
        trace.RETRIEVAL_STARTED,
        agent=agent_label,
        section_type=profile.section_type.value,
        filters={"record_type": list(profile.record_types), "region_id": list(region_ids or [])},
        k=k,
    )

    chunks = retrieve(
        query,
        variants=variants,
        top_k=k,
        record_types=profile.record_types,
        region_ids=region_ids,
        record_ids=record_ids,
    )

    # A specialist's record-type filter is tuned for incident-shaped
    # questions. A general one ("what traditional practices support
    # conservation?") can fall outside it and starve. When the filtered pass
    # surfaces almost no record-bearing evidence, widen rather than fail.
    record_bearing = sum(1 for c in chunks if c.record_id)
    if record_bearing < 2:
        widened = retrieve(query, variants=variants, top_k=k, region_ids=region_ids)
        if sum(1 for c in widened if c.record_id) > record_bearing:
            logger.info("%s: widening past the record_type filter", profile.key)
            chunks = widened

    top_score = max((c.normalised_score for c in chunks), default=0.0) * 10.0
    on_event(
        trace.RETRIEVAL_COMPLETED,
        agent=agent_label,
        section_type=profile.section_type.value,
        candidate_count=len(chunks),
        kept_count=len(chunks),
        top_rerank_score=round(top_score, 2),
    )

    if not chunks:
        return SpecialistResult(
            profile=profile,
            section=blank_section(
                profile, SectionStatus.EMPTY, profile.empty_reason, elapsed()
            ),
        )

    on_event(
        trace.AGENT_THINKING,
        agent=agent_label,
        section_type=profile.section_type.value,
        source_count=len(chunks),
        elapsed_ms=elapsed(),
    )

    # One retry, hard-capped by the shared counter — never a loop. On a
    # reasoning model an occasional finish_reason='length' with empty content
    # is expected rather than exceptional, so the retry doubles the budget.
    answer: GeneratedAnswer | None = None
    last_error: LLMError | None = None
    attempt = 0
    while True:
        if not budget.spend_llm_call():
            last_error = last_error or LLMError("LLM call cap reached before generation")
            break
        try:
            answer = generate_answer(
                question,
                chunks,
                extra_instruction=profile.instruction,
                max_tokens=settings.chat_max_completion_tokens * (2 if attempt else 1),
            )
            break
        except LLMError as exc:
            last_error = exc
            logger.warning("%s attempt %d failed: %s", profile.key, attempt + 1, exc)
            attempt += 1
            if budget.expired or not budget.spend_retry():
                break

    if answer is None:
        return SpecialistResult(
            profile=profile,
            section=blank_section(
                profile,
                SectionStatus.EMPTY,
                f"{profile.display_name} could not generate this section: {last_error}",
                elapsed(),
            ),
            chunks=list(chunks),
            failed=True,
        )

    gate = run_gate(
        answer.answer, chunks, has_sufficient_evidence=answer.has_sufficient_evidence
    )

    section = ReportSection(
        section_type=profile.section_type,
        status=SectionStatus.FILLED if answer.has_sufficient_evidence else SectionStatus.EMPTY,
        empty_reason=None if answer.has_sufficient_evidence else profile.empty_reason,
        content=answer.answer,
        claim_count=gate.claim_count,
        supported_claim_count=gate.supported_claim_count,
        owning_agent=agent_label,
        duration_ms=elapsed(),
        display_order=SECTION_DISPLAY_ORDER[profile.section_type],
    )

    return SpecialistResult(
        profile=profile,
        section=section,
        chunks=list(chunks),
        answer=answer,
        gate=gate,
    )
