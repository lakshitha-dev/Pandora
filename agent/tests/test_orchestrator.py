"""Dispatch, degradation, and assembly — SOLUTION.md §5.5.

Every test here stubs `run_specialist`, so nothing touches Azure. What is
being verified is the orchestration contract: that dispatch is genuinely
concurrent, that a timeout produces a partial report rather than an error,
and that the honest states are reachable.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from app.agents import orchestrator, trace
from app.agents.budget import Budget
from app.agents.routing import Classification
from app.agents.specialists import (
    EMERGENCY_RESPONDER,
    INCIDENT_INVESTIGATOR,
    MARINE_LIFE_PROTECTOR,
    SpecialistProfile,
    SpecialistResult,
    blank_section,
)
from app.agents.trace import TraceEmitter
from app.models.schemas import (
    Grounding,
    ReportSection,
    SectionStatus,
    SectionType,
    SitrepRequest,
)

ALL_THREE = [MARINE_LIFE_PROTECTOR, INCIDENT_INVESTIGATOR, EMERGENCY_RESPONDER]


def filled_result(profile: SpecialistProfile, content: str = "A grounded claim [INC-001].") -> SpecialistResult:
    return SpecialistResult(
        profile=profile,
        section=ReportSection(
            section_type=profile.section_type,
            status=SectionStatus.FILLED,
            content=content,
            claim_count=1,
            supported_claim_count=1,
            owning_agent=profile.key,
        ),
    )


def make_budget(seconds: float = 45) -> Budget:
    return Budget(deadline=time.perf_counter() + seconds, max_llm_calls=8, max_retries=1)


def make_classification() -> Classification:
    return Classification(original="q", rewritten="q")


# ── concurrency is real, not claimed ─────────────────────────────────────


@pytest.mark.asyncio
async def test_specialists_are_dispatched_concurrently(monkeypatch):
    """Wall clock must be the slowest specialist, not the sum. Three 0.3 s
    specialists sequentially would take 0.9 s."""

    def slow(profile, question, **kwargs):
        time.sleep(0.3)
        return filled_result(profile)

    monkeypatch.setattr(orchestrator, "run_specialist", slow)
    started = time.perf_counter()
    results = await orchestrator._dispatch(
        ALL_THREE,
        ["q"] * 3,
        budget=make_budget(),
        emitter=TraceEmitter(),
        classification=make_classification(),
    )
    elapsed = time.perf_counter() - started

    assert len(results) == 3
    assert all(r.filled for r in results)
    assert elapsed < 0.75, f"dispatch took {elapsed:.2f}s — that is sequential, not parallel"


@pytest.mark.asyncio
async def test_all_three_sections_begin_filling_before_any_completes(monkeypatch):
    """The visual that sells the architecture: three orbs igniting at once.
    If a section.completed lands before the third section.filling, the
    frontend animation degrades to a sequential list."""

    def slow(profile, question, **kwargs):
        time.sleep(0.2)
        return filled_result(profile)

    monkeypatch.setattr(orchestrator, "run_specialist", slow)
    emitter = TraceEmitter()
    await orchestrator._dispatch(
        ALL_THREE, ["q"] * 3, budget=make_budget(), emitter=emitter,
        classification=make_classification(),
    )

    steps = [e.step_type for e in emitter.events]
    first_completed = steps.index(trace.SECTION_COMPLETED)
    filling_before = steps[:first_completed].count(trace.SECTION_FILLING)
    assert filling_before == 3, "all three sections must start before the first finishes"


# ── rung 2: a timeout is a partial report, not an error ──────────────────


@pytest.mark.asyncio
async def test_a_timed_out_specialist_still_ships_the_report(monkeypatch):
    def one_hangs(profile, question, **kwargs):
        if profile.key == MARINE_LIFE_PROTECTOR.key:
            time.sleep(5)
        return filled_result(profile)

    monkeypatch.setattr(orchestrator, "run_specialist", one_hangs)
    monkeypatch.setattr(
        orchestrator.get_settings(), "agent_timeout_seconds", 1, raising=False
    )

    emitter = TraceEmitter()
    results = await orchestrator._dispatch(
        ALL_THREE, ["q"] * 3, budget=make_budget(), emitter=emitter,
        classification=make_classification(),
    )

    by_key = {r.profile.key: r for r in results}
    timed_out = by_key[MARINE_LIFE_PROTECTOR.key]
    assert timed_out.section.status == SectionStatus.TIMED_OUT
    assert timed_out.failed
    assert "Marine-Life Protector" in (timed_out.section.empty_reason or "")
    assert "Affected Species" in (timed_out.section.empty_reason or "")

    # The other two are unaffected — sections are independent by construction.
    assert by_key[INCIDENT_INVESTIGATOR.key].filled
    assert by_key[EMERGENCY_RESPONDER.key].filled
    assert trace.AGENT_TIMED_OUT in [e.step_type for e in emitter.events]


@pytest.mark.asyncio
async def test_a_crashing_specialist_does_not_crash_the_report(monkeypatch):
    def one_explodes(profile, question, **kwargs):
        if profile.key == EMERGENCY_RESPONDER.key:
            raise RuntimeError("boom")
        return filled_result(profile)

    monkeypatch.setattr(orchestrator, "run_specialist", one_explodes)
    results = await orchestrator._dispatch(
        ALL_THREE, ["q"] * 3, budget=make_budget(), emitter=TraceEmitter(),
        classification=make_classification(),
    )
    by_key = {r.profile.key: r for r in results}
    assert by_key[EMERGENCY_RESPONDER.key].failed
    assert by_key[MARINE_LIFE_PROTECTOR.key].filled


# ── section shape ────────────────────────────────────────────────────────


def test_undispatched_sections_render_not_applicable_never_blank():
    """Focused mode dispatches one specialist. The other two sections must
    say why they are empty — a blank section looks like a bug (§2.1 rule 3)."""
    sections = orchestrator._build_sections([filled_result(MARINE_LIFE_PROTECTOR)])
    assert len(sections) == 3
    by_type = {s.section_type: s for s in sections}
    assert by_type[SectionType.AFFECTED_SPECIES].status == SectionStatus.FILLED
    for st in (SectionType.LIKELY_CAUSES, SectionType.RECOMMENDED_ACTIONS):
        assert by_type[st].status == SectionStatus.NOT_APPLICABLE
        assert by_type[st].empty_reason


def test_sections_always_come_back_in_display_order():
    sections = orchestrator._build_sections([filled_result(p) for p in ALL_THREE])
    assert [s.section_type for s in sections] == [
        SectionType.AFFECTED_SPECIES,
        SectionType.LIKELY_CAUSES,
        SectionType.RECOMMENDED_ACTIONS,
    ]
    assert [s.display_order for s in sections] == [2, 3, 4]


# ── grounding merge ──────────────────────────────────────────────────────


def test_grounding_merge_takes_the_worst_case_per_rule():
    """A rule that failed in any section must show as failed for the report.
    Averaging pass/fail would hide a real grounding failure."""
    from app.chains.grounding_gate import GateResult
    from app.models.schemas import GroundingRuleResult

    def rules(passed_rule_1: bool) -> list[GroundingRuleResult]:
        return [
            GroundingRuleResult(
                number=n, name=f"rule {n}", passed=passed_rule_1 if n == 1 else True, detail=""
            )
            for n in range(1, 9)
        ]

    gates = [
        GateResult(groundedness=100, rules=rules(True)),
        GateResult(groundedness=50, rules=rules(False)),
    ]
    merged = orchestrator._merge_grounding(gates)
    assert merged.groundedness == 75, "groundedness is the mean"
    assert merged.rules[0].passed is False, "rule 1 failed somewhere, so it failed overall"


def test_grounding_merge_of_nothing_is_zero_not_a_crash():
    merged = orchestrator._merge_grounding([])
    assert merged == Grounding(groundedness=0, rules=[], unsupported_sentences=[])


# ── confidence always states its reason (§4.6) ───────────────────────────


@pytest.mark.parametrize(
    "groundedness,top,sources,conflicts,expected",
    [
        (96, 8.0, 5, False, "high"),
        (96, 8.0, 5, True, "moderate"),
        (75, 6.0, 3, False, "moderate"),
        (50, 5.0, 2, False, "low"),
        (10, 5.0, 1, False, "insufficient"),
        (100, 9.0, 0, False, "insufficient"),
    ],
)
def test_confidence_levels(groundedness, top, sources, conflicts, expected):
    level, reason = orchestrator._confidence(groundedness, top, sources, conflicts)
    assert level == expected
    assert reason, "a bare confidence number is not explainable — the reason is required"


# ── conflicts are presented, never resolved (§14.3) ──────────────────────


def make_chunk(cid: str, content: str, quality: str = "disputed report"):
    from app.chains.retrieval import RetrievedChunk

    return RetrievedChunk(
        chunk_id=cid, content=content, record_id=cid, record_type="field_note",
        title=cid, chapter="14", section="14.3", region_id="REG-01",
        evidence_quality=quality, risk_level="", record_date="2026-06-05",
        document_id="d", document_name="corpus", page=47, score=0.02,
    )


def test_disputed_records_produce_a_conflict_with_every_position_kept():
    chunks = [
        make_chunk("FN-A", "Plankton bloom after three calm hot days; no chemical odor."),
        make_chunk("FN-B", "Upstream pigment workshop maintenance; entry was never confirmed."),
        make_chunk("LAB-C", "Elevated carbonate particles but the chain of custody form was incomplete."),
    ]
    conflicts = orchestrator._detect_conflicts(chunks)
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert set(conflict.record_ids) == {"FN-A", "FN-B", "LAB-C"}
    assert len(conflict.positions) == 3, "every position is kept — none is picked as the winner"
    assert "chain of custody" in conflict.reliability_limitation
    assert conflict.resolution_recommendation


def test_a_single_disputed_record_is_not_a_conflict():
    assert orchestrator._detect_conflicts([make_chunk("FN-A", "one note")]) == []


def test_verified_records_are_not_a_conflict():
    chunks = [
        make_chunk("WS-01", "reading", quality="verified observation"),
        make_chunk("WS-02", "reading", quality="verified observation"),
    ]
    assert orchestrator._detect_conflicts(chunks) == []


# ── the honesty flip (§4.6) ──────────────────────────────────────────────


def test_insufficient_evidence_carries_the_briefs_mandated_sentence_verbatim():
    from app.chains.generation import INSUFFICIENT_EVIDENCE_MESSAGE

    evidence = orchestrator._insufficient_evidence(
        ["fauna", "flora"], [make_chunk("FAU-001", "some species record")]
    )
    # Exact equality, not `in`: the brief mandates this sentence and the 20-mark
    # Accuracy criterion turns on it. Reworded or templated-over is a failure.
    assert evidence.message == INSUFFICIENT_EVIDENCE_MESSAGE
    assert evidence.banner, "the actionable headline occupies its own slot"
    assert "fauna" in evidence.searched_scope, "a refusal must say what was searched"
    assert [m.record_id for m in evidence.closest_matches] == ["FAU-001"], (
        "closest partial matches turn a refusal into a next step"
    )
    assert "investigation" in evidence.what_would_resolve


def test_insufficient_evidence_text_renders_the_structured_object():
    """The prose form is only fallback content for an otherwise empty section."""
    evidence = orchestrator._insufficient_evidence(
        ["fauna"], [make_chunk("FAU-001", "some species record")]
    )
    text = orchestrator._insufficient_evidence_text(evidence)
    assert text.startswith(evidence.message), "the wording is non-negotiable"
    assert "Searched:" in text
    assert "FAU-001" in text


def assemble_with(results, emitter=None):
    return orchestrator._assemble(
        SitrepRequest(question="q"),
        make_classification(),
        results,
        make_budget(),
        time.perf_counter(),
        "sitrep",
        emitter or TraceEmitter(),
    )


def cited_result(profile, chunk, content="A claim [INC-001]."):
    """A section that generated text and cited a retrieved record."""
    from app.chains.generation import GeneratedAnswer
    from app.chains.grounding_gate import GateResult
    from app.models.schemas import GroundingRuleResult

    r = filled_result(profile, content)
    r.chunks = [chunk]
    r.answer = GeneratedAnswer(
        answer=content, cited_record_ids=[chunk.citation_id], has_sufficient_evidence=True
    )
    r.gate = GateResult(
        groundedness=100,
        rules=[GroundingRuleResult(number=n, name=f"r{n}", passed=True, detail="") for n in range(1, 9)],
        claim_count=1,
        supported_claim_count=1,
    )
    return r


def test_weak_retrieval_alone_flips_the_report_to_insufficient():
    """An off-corpus question ("population of Tokyo?") still returns records
    from hybrid search, and the model still cites one. Only the score knows
    the corpus does not cover it — so weak retrieval must be an INDEPENDENT
    trigger, not one gated behind having no citations at all."""
    weak = make_chunk("INC-001", "barely related text", quality="verified observation")
    weak.score = 0.001  # normalised ~0.03 -> 0.3/10, far below the 4.5 threshold

    response = assemble_with([cited_result(INCIDENT_INVESTIGATOR, weak)])

    assert response.top_rerank_score < 4.5
    assert response.has_sufficient_evidence is False, (
        "weak retrieval must flip the report even when a citation resolved"
    )
    assert response.insufficient_evidence
    assert response.situation_report.confidence_level == "insufficient"


def test_strong_retrieval_with_citations_stays_sufficient():
    strong = make_chunk("INC-001", "directly relevant", quality="verified observation")
    strong.score = 0.03  # normalised ~0.9 -> 9.0/10

    response = assemble_with([cited_result(INCIDENT_INVESTIGATOR, strong)])

    assert response.top_rerank_score >= 4.5
    assert response.has_sufficient_evidence is True
    assert response.insufficient_evidence is None


def test_rung_four_returns_a_report_not_an_error():
    """Retrieval itself failing must still produce a renderable report."""
    response = orchestrator._insufficient_response(
        SitrepRequest(question="q"), make_budget(), time.perf_counter(), reason="search unreachable"
    )
    assert response.has_sufficient_evidence is False
    assert len(response.situation_report.sections) == 3
    assert response.insufficient_evidence
    assert response.situation_report.confidence_level == "insufficient"
