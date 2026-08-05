"""The orchestrator — SOLUTION.md §5.2, §5.5, §5.4.

Ties classification, routing, concurrent dispatch, validation, and assembly
into one Situation Report, with a live SSE trace and a hard degradation
ladder. This is the only module that is allowed to *call* Layer 1's
retriever, Layer 2's generator, and Layer 4's gate — it never edits them
(SOLUTION.md §15, risk 14).

No recursion anywhere. The call graph is a fixed-depth tree by construction:
orchestrator -> specialists -> done. A specialist cannot dispatch another
specialist (docs/API_CONTRACT.md §2.3).

Degradation ladder, all four rungs live runtime paths, never a separate plan:
  1. all specialists return                    -> complete report
  2. some time out                              -> partial report, still ships
  3. all specialists fail, retrieval succeeded  -> single-agent fallback
  4. retrieval itself fails                     -> the honesty flip
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Sequence

from app.agents import routing, trace
from app.agents.budget import Budget
from app.agents.routing import Classification
from app.agents.specialists import (
    EMERGENCY_RESPONDER,
    INCIDENT_INVESTIGATOR,
    MARINE_LIFE_PROTECTOR,
    SpecialistProfile,
    SpecialistResult,
    blank_section,
    run_specialist,
)
from app.agents.trace import TraceEmitter
from app.chains.generation import INSUFFICIENT_EVIDENCE_MESSAGE
from app.chains.grounding_gate import GateResult
from app.chains.retrieval import RetrievedChunk
from app.core.config import get_settings
from app.core.llm import LLMError, chat
from app.models.schemas import (
    SECTION_DISPLAY_ORDER,
    Citation,
    Conflict,
    ConflictPosition,
    Grounding,
    GroundingRuleResult,
    ReportSection,
    SectionStatus,
    SectionType,
    SitrepRequest,
    SitrepResponse,
    SituationReport,
)

logger = logging.getLogger(__name__)

CONTENT_SECTIONS: tuple[SectionType, ...] = (
    SectionType.AFFECTED_SPECIES,
    SectionType.LIKELY_CAUSES,
    SectionType.RECOMMENDED_ACTIONS,
)
SECTION_LABEL: dict[SectionType, str] = {
    SectionType.AFFECTED_SPECIES: "Affected Species",
    SectionType.LIKELY_CAUSES: "Likely Causes",
    SectionType.RECOMMENDED_ACTIONS: "Recommended Actions",
}
# Priority order for the sequential single-agent fallback: causes first
# (an incident lead's first question is always "what happened"), then
# actions, then species — filled until the budget runs out.
SEQUENTIAL_ORDER: tuple[SpecialistProfile, ...] = (
    INCIDENT_INVESTIGATOR,
    EMERGENCY_RESPONDER,
    MARINE_LIFE_PROTECTOR,
)


# ─────────────────────────────────────────────────────────────────────────
# Section helpers
# ─────────────────────────────────────────────────────────────────────────


def _not_applicable(section_type: SectionType) -> ReportSection:
    return ReportSection(
        section_type=section_type,
        status=SectionStatus.NOT_APPLICABLE,
        empty_reason="Not applicable to this query",
        owning_agent="orchestrator",
        display_order=SECTION_DISPLAY_ORDER[section_type],
    )


def _build_sections(dispatched: Sequence[SpecialistResult]) -> list[ReportSection]:
    """The frozen three-content-section shape. Anything not dispatched (the
    other two specialists in focused mode) renders not_applicable — never a
    blank, per SOLUTION.md §2.1 rule 3."""
    by_type = {r.section.section_type: r.section for r in dispatched}
    sections: list[ReportSection] = []
    for section_type in CONTENT_SECTIONS:
        section = by_type.get(section_type) or _not_applicable(section_type)
        # Stamped here rather than trusted from the producer: this is the one
        # place the final report shape is assembled, and the frontend orders
        # the SITREP by this field.
        section.display_order = SECTION_DISPLAY_ORDER[section_type]
        sections.append(section)
    return sections


# ─────────────────────────────────────────────────────────────────────────
# Concurrent dispatch (§5.5 — wall clock is the slowest agent, not the sum)
# ─────────────────────────────────────────────────────────────────────────


async def _dispatch(
    profiles: Sequence[SpecialistProfile],
    questions: Sequence[str],
    *,
    budget: Budget,
    emitter: TraceEmitter,
    classification: Classification,
    owning_agent_override: str | None = None,
) -> list[SpecialistResult]:
    settings = get_settings()

    async def run_one(profile: SpecialistProfile, question: str) -> SpecialistResult:
        emitter.emit(
            trace.SECTION_FILLING,
            section_type=profile.section_type.value,
            owning_agent=owning_agent_override or profile.key,
        )
        timeout = max(1.0, min(settings.agent_timeout_seconds, budget.remaining_seconds))
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    run_specialist,
                    profile,
                    question,
                    budget=budget,
                    on_event=emitter.emit,
                    variants=classification.variants,
                    region_ids=classification.region_ids or None,
                    record_ids=classification.record_ids or None,
                    owning_agent=owning_agent_override,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            # A timed-out asyncio.to_thread worker is abandoned, not killed —
            # Python cannot interrupt a thread blocked in a socket read. Its
            # eventual result (if any) is simply discarded.
            #
            # Logged, not just traced: a silent timeout is indistinguishable
            # from a crash in the server log, and "all specialists failed" with
            # no preceding line is unaffordably hard to diagnose on the clock.
            logger.warning(
                "%s timed out after %.1fs (budget had %.1fs left)",
                profile.key, timeout, budget.remaining_seconds,
            )
            emitter.emit(
                trace.AGENT_TIMED_OUT,
                agent=profile.key,
                section_type=profile.section_type.value,
                elapsed_ms=int(timeout * 1000),
            )
            return SpecialistResult(
                profile=profile,
                section=blank_section(
                    profile,
                    SectionStatus.TIMED_OUT,
                    f"{profile.display_name} did not respond within {int(timeout)} s — "
                    f"{SECTION_LABEL[profile.section_type]} unavailable for this report.",
                    int(timeout * 1000),
                ),
                failed=True,
            )
        except Exception as exc:  # noqa: BLE001 - one crashed specialist must not crash the report
            logger.exception("%s crashed", profile.key)
            return SpecialistResult(
                profile=profile,
                section=blank_section(
                    profile, SectionStatus.EMPTY, f"{profile.display_name} failed: {exc}"
                ),
                failed=True,
            )

        if result.filled:
            emitter.emit(
                trace.SECTION_COMPLETED,
                section_type=profile.section_type.value,
                claim_count=result.section.claim_count,
                source_count=len(result.chunks),
                duration_ms=result.section.duration_ms,
            )
            emitter.emit(
                trace.AGENT_COMPLETED,
                agent=owning_agent_override or profile.key,
                claim_count=result.section.claim_count,
                source_count=len(result.chunks),
                duration_ms=result.section.duration_ms,
            )
        else:
            emitter.emit(
                trace.SECTION_UNAVAILABLE,
                section_type=profile.section_type.value,
                empty_reason=result.section.empty_reason,
            )
        return result

    return list(await asyncio.gather(*(run_one(p, q) for p, q in zip(profiles, questions))))


def _sequential_fill(
    profiles: Sequence[SpecialistProfile],
    question: str,
    *,
    budget: Budget,
    emitter: TraceEmitter,
    classification: Classification,
) -> list[SpecialistResult]:
    """Rung 3 / the AGENTIC_ENABLED=false path: same primitives, one at a
    time, budget-aware. Stops filling and marks the remainder unavailable
    rather than overrunning the orchestration budget."""
    results: list[SpecialistResult] = []
    for profile in profiles:
        if budget.expired:
            results.append(
                SpecialistResult(
                    profile=profile,
                    section=blank_section(
                        profile,
                        SectionStatus.EMPTY,
                        "Orchestration budget exhausted before this section could be filled.",
                    ),
                )
            )
            continue
        emitter.emit(
            trace.SECTION_FILLING, section_type=profile.section_type.value, owning_agent="single_agent"
        )
        result = run_specialist(
            profile,
            question,
            budget=budget,
            on_event=emitter.emit,
            variants=classification.variants,
            region_ids=classification.region_ids or None,
            record_ids=classification.record_ids or None,
            owning_agent="single_agent",
        )
        if result.filled:
            emitter.emit(
                trace.SECTION_COMPLETED,
                section_type=profile.section_type.value,
                claim_count=result.section.claim_count,
                source_count=len(result.chunks),
                duration_ms=result.section.duration_ms,
            )
        else:
            emitter.emit(
                trace.SECTION_UNAVAILABLE,
                section_type=profile.section_type.value,
                empty_reason=result.section.empty_reason,
            )
        results.append(result)
    return results


# ─────────────────────────────────────────────────────────────────────────
# Compare-mode synthesis
# ─────────────────────────────────────────────────────────────────────────

_SYNTHESIS_SYSTEM = """You write a side-by-side comparison for a Pandora Situation Report.

You are given two independently-researched, already-grounded briefs. Combine them into one \
comparison, presented side by side under clear sub-headings, that keeps every citation from both. \
Do not drop a citation, do not invent a new claim, and do not blend a fact from one subject into \
the other's mention of it — the no-merging rule that produced each brief still applies to how you \
present them together."""


def _synthesize_compare(
    question: str, subs: Sequence[str], results: Sequence[SpecialistResult], *, budget: Budget
) -> str:
    filled = [r for r in results if r.filled]
    if len(filled) < 2:
        content = "\n\n".join(r.section.content for r in results if r.section.content)
        return content or "Insufficient evidence was retrieved for one or both sides of this comparison."

    if not budget.spend_llm_call():
        parts = [f"### {sub}\n\n{r.section.content}" for sub, r in zip(subs, results)]
        return "\n\n---\n\n".join(parts)

    a, b = filled[0], filled[1]
    label_a = subs[0] if len(subs) > 0 else a.profile.display_name
    label_b = subs[1] if len(subs) > 1 else b.profile.display_name
    user = (
        f"ORIGINAL QUESTION\n{question}\n\n"
        f"BRIEF A — {label_a}\n{a.section.content}\n\n"
        f"BRIEF B — {label_b}\n{b.section.content}"
    )
    try:
        return chat(
            [
                {"role": "system", "content": _SYNTHESIS_SYSTEM},
                {"role": "user", "content": user},
            ],
            max_tokens=get_settings().chat_max_completion_tokens,
        )
    except LLMError as exc:
        logger.warning("compare synthesis failed, presenting briefs unmerged: %s", exc)
        parts = [f"### {sub}\n\n{r.section.content}" for sub, r in zip(subs, results)]
        return "\n\n---\n\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────
# Assembly — citations, grounding, conflicts, confidence
# ─────────────────────────────────────────────────────────────────────────


def _pool_chunks(results: Sequence[SpecialistResult]) -> list[RetrievedChunk]:
    by_id: dict[str, RetrievedChunk] = {}
    for r in results:
        for c in r.chunks:
            by_id.setdefault(c.chunk_id, c)
    return list(by_id.values())


def _assemble_citations(results: Sequence[SpecialistResult]) -> list[Citation]:
    """Deduplicated union of every chunk cited by any section, renumbered."""
    order: list[str] = []
    by_id: dict[str, RetrievedChunk] = {}
    for r in results:
        if not r.answer:
            continue
        chunk_by_cite = {c.citation_id: c for c in r.chunks}
        for rid in r.answer.cited_record_ids:
            chunk = chunk_by_cite.get(rid)
            if chunk and rid not in by_id:
                by_id[rid] = chunk
                order.append(rid)

    citations: list[Citation] = []
    for i, rid in enumerate(order):
        chunk = by_id[rid]
        data = chunk.to_citation(i + 1)
        citations.append(
            Citation(**{**data, "record_type": chunk.record_type, "rerank_score": chunk.rerank_score})
        )
    return citations


def _merge_grounding(gates: Sequence[GateResult]) -> Grounding:
    """Worst-case pass per rule, mean groundedness across sections."""
    if not gates:
        return Grounding(groundedness=0, rules=[], unsupported_sentences=[])

    merged_rules: list[GroundingRuleResult] = []
    for number in range(1, 9):
        per = [g.rules[number - 1] for g in gates if len(g.rules) >= number]
        if not per:
            continue
        failed = [r for r in per if not r.passed]
        merged_rules.append(failed[0] if failed else per[0])

    return Grounding(
        groundedness=round(sum(g.groundedness for g in gates) / len(gates)),
        rules=merged_rules,
        unsupported_sentences=[s for g in gates for s in g.unsupported_sentences],
    )


_LIMITATION_HINTS: tuple[tuple[str, str], ...] = (
    ("chain-of-custody", "incomplete chain of custody on the laboratory sample"),
    ("chain of custody", "incomplete chain of custody on the laboratory sample"),
    ("not directly comparable", "survey effort not normalised between counts"),
    ("unconfirmed", "observation was never independently confirmed"),
)


def _reliability_limitation(text: str) -> str:
    lowered = text.lower()
    for needle, label in _LIMITATION_HINTS:
        if needle in lowered:
            return label
    return "unverified or challenged evidence"


def _detect_conflicts(all_chunks: Sequence[RetrievedChunk]) -> list[Conflict]:
    """Structural signal, mirroring GroundingGate rule 7 but with full
    per-position detail for the report's conflict panel (API §1.1): two or
    more retrieved records carrying the corpus's own 'disputed report'
    evidence label describe contested evidence for the same event. Every
    position is kept, none is picked as the winner (§14.3)."""
    disputed = [c for c in all_chunks if c.evidence_quality == "disputed report"]
    if len(disputed) < 2:
        return []

    positions = [
        ConflictPosition(
            record_id=c.citation_id,
            claim=c.excerpt(200),
            evidence_quality=c.evidence_quality,
            reliability_limitation=_reliability_limitation(c.content),
        )
        for c in disputed
    ]
    return [
        Conflict(
            record_ids=[c.citation_id for c in disputed],
            nature="Retrieved records disagree or carry unverified evidence about the same event",
            reliability_limitation=_reliability_limitation(" ".join(c.content for c in disputed)),
            positions=positions,
            resolution_recommendation="Recommend additional properly documented sampling to resolve the discrepancy.",
        )
    ]


def _confidence(
    groundedness: int, top_score_10: float, source_count: int, has_conflicts: bool
) -> tuple[str, str]:
    """§4.6's confidence table — always states its reason, never a bare number."""
    if source_count == 0:
        return "insufficient", "no record scored above the relevance threshold"
    if groundedness >= 90 and top_score_10 >= 7.5 and source_count >= 3 and not has_conflicts:
        return "high", f"High — {source_count} sources, groundedness {groundedness}%, no conflicts"
    if has_conflicts:
        return "moderate", f"Moderate — {source_count} sources, 1 unresolved conflict, chain of custody incomplete"
    if groundedness >= 70:
        return "moderate", f"Moderate — {source_count} sources, groundedness {groundedness}%"
    if groundedness >= 40:
        return "low", f"Low — {source_count} sources, groundedness {groundedness}%"
    return "insufficient", "no record scored above the relevance threshold"


def _insufficient_evidence_text(
    record_types_searched: Sequence[str], all_chunks: Sequence[RetrievedChunk]
) -> str:
    scope = ", ".join(sorted(set(record_types_searched))) or "the full Pandora knowledge base"
    lines = [INSUFFICIENT_EVIDENCE_MESSAGE, "", f"Searched: {scope}."]
    top = sorted(all_chunks, key=lambda c: c.normalised_score, reverse=True)[:3]
    if top:
        closest = "; ".join(f"{c.citation_id} (score {c.normalised_score:.2f})" for c in top)
        lines.append(f"Closest partial matches, below the confidence threshold: {closest}.")
    lines.append("Recommend field investigation and additional properly documented sampling to resolve this.")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────


async def run_sitrep(req: SitrepRequest, emitter: TraceEmitter) -> SitrepResponse:
    settings = get_settings()
    started = time.perf_counter()
    budget = Budget.start(settings)

    emitter.emit(trace.QUERY_RECEIVED, question=req.question)

    try:
        return await _run(req, emitter, budget, settings, started)
    except Exception as exc:  # noqa: BLE001 - rung 4: never let a crash reach the client
        logger.exception("orchestration failed for %r", req.question[:80])
        emitter.emit(trace.ERROR, code="internal_error", message=str(exc)[:300])
        response = _insufficient_response(
            req, budget, started, reason=f"orchestration failed: {exc}"
        )
        emitter.emit(
            trace.ANSWER_COMPLETED,
            llm_call_count=budget.llm_calls,
            latency_ms=response.duration_ms,
            citation_count=0,
            has_sufficient_evidence=False,
            assembly_mode=response.situation_report.assembly_mode,
            was_partial=True,
        )
        emitter.close()
        return response


def _insufficient_response(
    req: SitrepRequest, budget: Budget, started: float, *, reason: str
) -> SitrepResponse:
    """Rung 4 — retrieval or classification itself failed. The honesty flip."""
    text = f"{INSUFFICIENT_EVIDENCE_MESSAGE}\n\n{reason}"
    sections = [
        ReportSection(
            section_type=st,
            status=SectionStatus.EMPTY,
            empty_reason=reason,
            content=text if st == SectionType.LIKELY_CAUSES else "",
            owning_agent="orchestrator",
            display_order=SECTION_DISPLAY_ORDER[st],
        )
        for st in CONTENT_SECTIONS
    ]
    return SitrepResponse(
        situation_report=SituationReport(
            assembly_mode="single_agent_fallback",
            confidence_level="insufficient",
            confidence_reason="the corpus could not be searched for this question",
            was_partial=True,
            sections=sections,
        ),
        grounding=Grounding(groundedness=0, rules=[], unsupported_sentences=[]),
        has_sufficient_evidence=False,
        insufficient_evidence=text,
        llm_call_count=budget.llm_calls,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


async def _run(
    req: SitrepRequest, emitter: TraceEmitter, budget: Budget, settings, started: float
) -> SitrepResponse:
    scale_chunks = await asyncio.to_thread(routing.retrieve_severity_scale)
    classification = await asyncio.to_thread(
        routing.classify,
        req.question,
        budget=budget,
        history=req.conversation_history,
        scale_chunks=scale_chunks,
    )
    routing.emit_classification(emitter, classification)

    if not settings.agentic_enabled:
        emitter.emit(
            trace.ROUTE_DECIDED,
            mode="single_agent",
            specialists=[p.key for p in SEQUENTIAL_ORDER],
            reason="AGENTIC_ENABLED is off → single-agent fill, identical report structure",
        )
        results = await asyncio.to_thread(
            _sequential_fill,
            SEQUENTIAL_ORDER,
            classification.rewritten,
            budget=budget,
            emitter=emitter,
            classification=classification,
        )
        return _assemble(req, classification, results, budget, started, "single_agent", emitter)

    mode, reason = routing.select_mode(req.question, classification, forced=req.mode)
    profiles = routing.specialists_for(mode, req.question, classification)
    questions = routing.sub_questions_for(mode, profiles, req.question, classification)
    emitter.emit(
        trace.ROUTE_DECIDED,
        mode=mode,
        specialists=[p.key for p in profiles],
        reason=reason,
    )

    results = await _dispatch(
        profiles, questions, budget=budget, emitter=emitter, classification=classification
    )

    # Rung 3: every dispatched specialist failed outright (timeout/crash),
    # but retrieval itself was reachable — fall back to a single-agent fill
    # over the same primitives rather than shipping an all-empty report.
    if results and all(r.failed for r in results):
        logger.warning(
            "rung 3: all %d specialists failed (%s) — falling back to single-agent fill",
            len(results),
            ", ".join(f"{r.profile.key}={r.section.status.value}" for r in results),
        )
        emitter.emit(
            trace.ROUTE_DECIDED,
            mode="single_agent_fallback",
            specialists=[p.key for p in SEQUENTIAL_ORDER],
            reason="All specialists failed → falling back to single-agent generation over retrieved evidence",
        )
        results = await asyncio.to_thread(
            _sequential_fill,
            SEQUENTIAL_ORDER,
            classification.rewritten,
            budget=budget,
            emitter=emitter,
            classification=classification,
        )
        return _assemble(
            req, classification, results, budget, started, "single_agent_fallback", emitter
        )

    if mode == "compare":
        emitter.emit(trace.SYNTHESIS_STARTED, input_count=len(results))
        subs = routing.compare_sub_queries(req.question, classification)
        synthesis = await asyncio.to_thread(
            _synthesize_compare, req.question, subs, results, budget=budget
        )
        if results and synthesis:
            results[0].section.content = synthesis

    return _assemble(req, classification, results, budget, started, mode, emitter)


def _assemble(
    req: SitrepRequest,
    classification: Classification,
    results: Sequence[SpecialistResult],
    budget: Budget,
    started: float,
    assembly_mode: str,
    emitter: TraceEmitter,
) -> SitrepResponse:
    settings = get_settings()
    sections = _build_sections(results)
    all_chunks = _pool_chunks(results)
    citations = _assemble_citations(results)

    gates = [r.gate for r in results if r.gate is not None]
    grounding = _merge_grounding(gates)
    emitter.emit(trace.VALIDATION_RUNNING, rule_count=8)
    emitter.emit(
        trace.VALIDATION_RESULT,
        rules=[r.model_dump() for r in grounding.rules],
        groundedness=grounding.groundedness,
    )

    conflicts = _detect_conflicts(all_chunks)
    for c in conflicts:
        emitter.emit(trace.CONFLICT_DETECTED, record_ids=c.record_ids, conflict_nature=c.nature)

    top_score_10 = max((c.normalised_score for c in all_chunks), default=0.0) * 10.0
    has_conflicts = bool(conflicts)
    confidence_level, confidence_reason = _confidence(
        grounding.groundedness, top_score_10, len(citations), has_conflicts
    )

    # Deterministic honesty-flip triggers (§4.6) — never model self-assessment,
    # because a model's read of its own uncertainty is unreliable and a rule is
    # not. Each trigger below is INDEPENDENT: any one of them flips the report.
    #
    # Weak retrieval matters most and is the easiest to get wrong. Hybrid
    # search always returns its top-k, so an off-corpus question ("what is the
    # population of Tokyo?") still comes back with records, and the model will
    # still cite one. Only the score says the corpus does not cover it.
    weak_retrieval = top_score_10 < settings.rerank_score_threshold * 10
    no_supported_claims = grounding.groundedness == 0 and bool(gates)
    no_claims_at_all = not citations
    nothing_filled = not any(s.status == SectionStatus.FILLED for s in sections)
    sufficient = not (
        weak_retrieval or no_supported_claims or no_claims_at_all or nothing_filled
    )

    record_types_searched = sorted({rt for r in results for rt in r.profile.record_types})
    insufficient_text = None
    if not sufficient:
        insufficient_text = _insufficient_evidence_text(record_types_searched, all_chunks)
        confidence_level, confidence_reason = "insufficient", "the corpus does not cover this question"
        for s in sections:
            if s.status == SectionStatus.EMPTY and not s.content:
                s.content = insufficient_text

    was_partial = any(r.section.status == SectionStatus.TIMED_OUT for r in results)

    region_ids = classification.region_ids or sorted(
        {c.region_id for c in all_chunks if c.region_id}
    )

    situation_report = SituationReport(
        priority_class=classification.severity_class,
        priority_reason=classification.severity_reason,
        priority_citation=classification.severity_citation,
        priority_label=classification.severity_label,
        priority_page=classification.severity_page,
        affected_region_ids=region_ids,
        assembly_mode=assembly_mode,
        confidence_level=confidence_level,
        confidence_reason=confidence_reason,
        was_partial=was_partial,
        sections=sections,
    )

    response = SitrepResponse(
        situation_report=situation_report,
        citations=citations,
        grounding=grounding,
        conflicts=conflicts,
        has_sufficient_evidence=sufficient,
        insufficient_evidence=insufficient_text,
        llm_call_count=budget.llm_calls,
        duration_ms=int((time.perf_counter() - started) * 1000),
        top_rerank_score=round(top_score_10, 2),
    )

    # The terminal event carries the COMPLETE response body, so a streaming
    # client never has to call the JSON endpoint (docs/API_CONTRACT.md §1.2).
    # Built as a dict rather than splatted with extra keywords: model_dump
    # already contains llm_call_count, and passing it again as a keyword is a
    # duplicate-keyword TypeError that would take down every successful
    # orchestration. `latency_ms` is the contract's name for duration_ms;
    # both are sent rather than renaming a frozen field.
    payload = response.model_dump(mode="json")
    payload["latency_ms"] = response.duration_ms
    emitter.emit(trace.ANSWER_COMPLETED, **payload)
    emitter.close()
    return response
