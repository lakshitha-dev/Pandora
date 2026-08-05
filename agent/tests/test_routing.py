"""Routing and classification — SOLUTION.md §5.2, §5.4.

Routing is deterministic on purpose: a hard limit enforced by rules, not by
asking a model nicely. These tests are the check on that.
"""

from __future__ import annotations

import pytest

from app.agents import routing
from app.agents.routing import Classification
from app.agents.specialists import (
    EMERGENCY_RESPONDER,
    INCIDENT_INVESTIGATOR,
    MARINE_LIFE_PROTECTOR,
    SPECIALISTS,
)
from app.chains.retrieval import RetrievedChunk
from app.models.schemas import PriorityClass


def make_classification(**kwargs) -> Classification:
    base = {"original": "q", "rewritten": "q"}
    base.update(kwargs)
    return Classification(**base)


def make_chunk(**kwargs) -> RetrievedChunk:
    defaults = dict(
        chunk_id="c1", content="body", record_id="", record_type="narrative",
        title="Water Incident Classification", chapter="4 · Water",
        section="4.5 Water Incident Classification", region_id="",
        evidence_quality="verified observation", risk_level="", record_date="",
        document_id="d1", document_name="corpus.md", page=12, score=0.02,
    )
    defaults.update(kwargs)
    return RetrievedChunk(**defaults)


# ── the roster is fixed at three (§5.3) ──────────────────────────────────


def test_specialist_roster_is_fixed_at_three():
    assert len(SPECIALISTS) == 3
    assert {p.section_type for p in SPECIALISTS.values()} == {
        MARINE_LIFE_PROTECTOR.section_type,
        INCIDENT_INVESTIGATOR.section_type,
        EMERGENCY_RESPONDER.section_type,
    }, "each specialist must own a distinct section"


# ── mode selection (§5.4) ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "question",
    [
        "Compare the recommended responses for water contamination and a volcanic event",
        "What is the difference between INC-001 and INC-005?",
        "Awa Reef versus the Luminous Shelf",
    ],
)
def test_comparison_language_routes_to_compare(question):
    mode, reason = routing.select_mode(question, make_classification())
    assert mode == "compare"
    assert "compare" in reason.lower()


def test_w_class_severity_routes_to_sitrep():
    mode, reason = routing.select_mode(
        "The water near Awa Reef has changed",
        make_classification(severity_class=PriorityClass.W3),
    )
    assert mode == "sitrep"
    assert "3 specialists in parallel" in reason


def test_observation_shaped_input_routes_to_sitrep_without_a_w_class():
    """Rung-safety: a plain observation must still get the full report even
    if the classifier declined to assign a severity."""
    mode, _ = routing.select_mode(
        "The water near Awa Reef has turned turquoise and the fish are leaving the area",
        make_classification(),
    )
    assert mode == "sitrep"


def test_single_topic_lookup_routes_to_focused():
    mode, _ = routing.select_mode(
        "what is the approach distance for a Deepbell Singer?", make_classification()
    )
    assert mode == "focused"


def test_caller_can_force_a_mode():
    mode, reason = routing.select_mode(
        "anything at all", make_classification(severity_class=PriorityClass.W4), forced="focused"
    )
    assert mode == "focused"
    assert "forced" in reason.lower()


# ── focused-mode signals (§5.4) ──────────────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("which species are vulnerable to contamination?", MARINE_LIFE_PROTECTOR),
        ("tell me about FAU-014", MARINE_LIFE_PROTECTOR),
        ("what should we do about the spill?", EMERGENCY_RESPONDER),
        ("what are the immediate actions for MED-003?", EMERGENCY_RESPONDER),
        ("what caused the turquoise water?", INCIDENT_INVESTIGATOR),
        ("investigate the readings at WS-03", INCIDENT_INVESTIGATOR),
    ],
)
def test_focused_signals_pick_the_right_specialist(text, expected):
    assert routing.focused_specialist(text).key == expected.key


def test_ambiguous_defaults_to_the_investigator():
    """The safest default — it is the one specialist forbidden from
    asserting a cause."""
    assert routing.focused_specialist("hmm").key == INCIDENT_INVESTIGATOR.key


# ── dispatch rosters (§5.5 caps) ─────────────────────────────────────────


def test_sitrep_dispatches_exactly_three():
    profiles = routing.specialists_for("sitrep", "the water changed", make_classification())
    assert len(profiles) == 3
    assert len({p.key for p in profiles}) == 3


def test_focused_dispatches_exactly_one():
    profiles = routing.specialists_for("focused", "which species?", make_classification())
    assert len(profiles) == 1


def test_compare_dispatches_two_distinct_specialists():
    c = make_classification(
        sub_queries=["what caused the water contamination", "what caused the vent plume"]
    )
    profiles = routing.specialists_for("compare", "compare them", c)
    assert len(profiles) == 2
    assert profiles[0].key != profiles[1].key, (
        "both sides must be retrieved through different lenses — that is the "
        "whole §5.1 justification for compare mode"
    )


def test_compare_sub_queries_split_on_the_conjunction_when_the_model_gives_none():
    subs = routing.compare_sub_queries(
        "compare water contamination and an underwater volcanic event", make_classification()
    )
    assert len(subs) == 2
    assert subs[0] != subs[1]


# ── severity must be cited or downgraded ─────────────────────────────────


def test_unresolvable_severity_citation_falls_back_to_the_retrieved_scale():
    c = make_classification(severity_class=PriorityClass.W3, severity_citation="MADE-UP")
    scale = [make_chunk(cite_key="SEC-1")]
    routing._apply_deterministic_overrides(c, "the water turned turquoise", scale)
    assert c.severity_class == PriorityClass.W3
    assert c.severity_citation == "4.5 Water Incident Classification"
    assert c.severity_page == 12


def test_severity_downgrades_to_informational_when_no_scale_was_retrieved():
    """An uncited severity is an ungrounded model opinion — exactly what the
    Accuracy criterion penalises."""
    c = make_classification(severity_class=PriorityClass.W4, severity_citation="SEC-1")
    routing._apply_deterministic_overrides(c, "the water turned turquoise", [])
    assert c.severity_class == PriorityClass.INFORMATIONAL
    assert c.severity_citation == ""


# ── record IDs come from the text, not from the model's imagination ──────


def test_record_ids_are_extracted_by_regex():
    c = make_classification()
    routing._apply_deterministic_overrides(c, "what does INC-005 say about WS-03?", [])
    assert "INC-005" in c.record_ids
    assert "WS-03" in c.record_ids


def test_invented_record_ids_are_dropped():
    c = make_classification(record_ids=["not an id", "lowercase-1"])
    routing._apply_deterministic_overrides(c, "a question", [])
    assert c.record_ids == []


def test_region_ids_are_extracted_and_drive_the_map():
    c = make_classification()
    routing._apply_deterministic_overrides(c, "the situation in REG-01", [])
    assert c.region_ids == ["REG-01"]
