"""Agent shape → contract shape. Pure functions, no I/O.

The agent service returns a *flat* situation report (`priority_class`,
`priority_reason`, `confidence_level`, …). API_CONTRACT §1.1 specifies a
*nested* one (`priority{}`, `confidence{}`). Rather than let that translation
smear across the ask service and the SSE handler, it lives here — one place,
unit-testable without a live agent or a database.

Everything in this module is deliberately total: an agent that emits an
unexpected enum value gets mapped onto a safe default rather than 500ing a
report that is otherwise perfectly good.
"""

import uuid

from app.db.models import CORPUS_DOCUMENT_ID, CORPUS_DOCUMENT_SLUG
from app.schemas import agent as ag
from app.schemas.ask import (
    ClosestMatch,
    ConfidenceBlock,
    Conflict,
    ConflictPosition,
    InsufficientEvidence,
    Priority,
    ReportSection,
    SituationReport,
)
from app.schemas.common import Citation

# The agent says "medium"; the contract says "moderate". Normalised in exactly
# one place so the two vocabularies never leak past this module.
_CONFIDENCE = {
    "high": "high",
    "moderate": "moderate",
    "medium": "moderate",
    "low": "low",
    "insufficient": "insufficient",
}

# The agent's PriorityClass enum spells the default "Informational".
_PRIORITY = {
    "w1": "W1",
    "w2": "W2",
    "w3": "W3",
    "w4": "W4",
    "informational": "informational",
}

_SECTION_TYPES = {"affected_species", "likely_causes", "recommended_actions"}
_OWNING_AGENTS = {
    "marine_life_protector",
    "incident_investigator",
    "emergency_responder",
    "orchestrator",
}
_SECTION_STATUSES = {"filled", "empty", "timed_out", "not_applicable"}

_DEFAULT_EMPTY_REASON = "No content was produced for this section."


def normalise_confidence(level: str) -> str:
    return _CONFIDENCE.get((level or "").strip().lower(), "insufficient")


def normalise_priority_class(value: str) -> str:
    return _PRIORITY.get((value or "").strip().lower(), "informational")


def map_priority(report: ag.RagSituationReport) -> Priority:
    """Nest the flat `priority_*` fields.

    A W-class with no citation is downgraded to `informational`: the contract
    states the citation is never null for a W-class, because an uncited severity
    is an ungrounded model opinion and the whole point is that it isn't one.
    """
    priority_class = normalise_priority_class(report.priority_class)
    citation = (report.priority_citation or "").strip() or None

    if priority_class != "informational" and citation is None:
        return Priority(
            **{"class": "informational"},
            label="OBSERVATION",
            reason=(
                report.priority_reason
                or "Severity could not be attributed to a corpus record."
            ),
            citation=None,
            page=None,
        )

    return Priority(
        **{"class": priority_class},
        label=report.priority_label or "OBSERVATION",
        reason=report.priority_reason or "",
        citation=citation,
        page=report.priority_page,
    )


def map_section(section: ag.RagReportSection) -> ReportSection | None:
    """Map one content section, or None if it isn't one of the three.

    The agent's SectionType enum also carries `priority`, `sources`, and
    `confidence`; those are the orchestrator's own top-level fields in §1.1,
    not rows in `sections`, so they are dropped here rather than duplicated.
    """
    section_type = (section.section_type or "").strip().lower()
    if section_type not in _SECTION_TYPES:
        return None

    status = (section.status or "").strip().lower()
    if status not in _SECTION_STATUSES:
        status = "empty"

    owning_agent = (section.owning_agent or "").strip().lower()
    if owning_agent not in _OWNING_AGENTS:
        owning_agent = "orchestrator"

    # `empty_reason` is non-null whenever status != "filled" — the UI renders it
    # as the honest explanation, so a blank one would show an empty card.
    empty_reason = section.empty_reason
    if status != "filled" and not empty_reason:
        empty_reason = _DEFAULT_EMPTY_REASON
    elif status == "filled":
        empty_reason = None

    return ReportSection(
        section_type=section_type,  # type: ignore[arg-type]
        owning_agent=owning_agent,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        empty_reason=empty_reason,
        content=section.content or "",
        claim_count=section.claim_count,
        supported_claim_count=section.supported_claim_count,
        duration_ms=section.duration_ms,
        display_order=section.display_order,
    )


def map_conflict(conflict: ag.Conflict) -> Conflict:
    """`nature` on the wire in Part 2 is `conflict_nature` in Part 1."""
    return Conflict(
        record_ids=list(conflict.record_ids),
        conflict_nature=conflict.nature or "",
        positions=[
            ConflictPosition(
                record_id=p.record_id,
                claim=p.claim,
                evidence_quality=p.evidence_quality,
                reliability_limitation=p.reliability_limitation,
            )
            for p in conflict.positions
        ],
        resolution_recommendation=conflict.resolution_recommendation or "",
    )


def map_situation_report(response: ag.SitrepResponse) -> SituationReport:
    sr = response.situation_report
    sections = [mapped for s in sr.sections if (mapped := map_section(s)) is not None]
    sections.sort(key=lambda s: s.display_order)

    return SituationReport(
        priority=map_priority(sr),
        affected_region_ids=list(sr.affected_region_ids),
        assembly_mode=sr.assembly_mode or "sitrep",
        sections=sections,
        confidence=ConfidenceBlock(
            level=normalise_confidence(sr.confidence_level),  # type: ignore[arg-type]
            reason=sr.confidence_reason or "",
            # Groundedness is measured by the GroundingGate, so it is carried
            # from `grounding`, not re-derived from the confidence label.
            groundedness=max(0, min(100, response.grounding.groundedness)),
        ),
        conflicts=[map_conflict(c) for c in response.conflicts],
        was_partial=sr.was_partial,
    )


def resolve_document_id(raw: str) -> uuid.UUID | None:
    """Agent-side document id → the gateway's UUID.

    The pre-indexed corpus is stamped with a slug rather than a UUID, so it is
    mapped onto the seeded corpus row. Anything else is an uploaded document,
    whose id already is a UUID.
    """
    if raw == CORPUS_DOCUMENT_SLUG:
        return CORPUS_DOCUMENT_ID
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError, TypeError):
        return None


def map_citation(citation: ag.RagCitation, document_id: uuid.UUID, name: str) -> Citation:
    return Citation(
        marker=citation.marker,
        document_id=document_id,
        document_name=name,
        chunk_id=citation.chunk_id,
        record_id=citation.record_id,
        record_type=citation.record_type,
        title=citation.title,
        chapter=citation.chapter,
        section=citation.section or None,
        page=citation.page,
        region_id=citation.region_id,
        excerpt=citation.excerpt,
        relevance_score=max(0.0, min(1.0, citation.relevance_score)),
        rerank_score=citation.rerank_score,
        evidence_quality=citation.evidence_quality,
        risk_level=citation.risk_level,
        record_date=citation.record_date,
    )


def map_insufficient_evidence(
    response: ag.SitrepResponse,
) -> InsufficientEvidence | None:
    """Non-null only when evidence is insufficient.

    `message` is copied through untouched — it is the brief's mandated sentence
    and a 20-mark criterion. It is never rebuilt or reworded here.
    """
    if response.has_sufficient_evidence:
        return None

    source = response.insufficient_evidence
    if source is None:
        return None

    return InsufficientEvidence(
        banner=source.banner,
        message=source.message,
        searched_scope=source.searched_scope,
        closest_matches=[
            ClosestMatch(
                record_id=m.record_id,
                title=m.title,
                relevance_score=m.relevance_score,
                page=m.page,
            )
            for m in source.closest_matches
        ],
        what_would_resolve=source.what_would_resolve,
    )


def flatten_for_history(report: SituationReport) -> str:
    """A plain-text rendering, stored only for next-turn coreference.

    Not what the frontend renders — that is the structured report. This exists
    so "what about the second one?" has something to resolve against.
    """
    parts: list[str] = []
    if report.priority.reason:
        parts.append(f"[{report.priority.label}] {report.priority.reason}")
    for section in report.sections:
        if section.status == "filled" and section.content:
            parts.append(f"{section.section_type}: {section.content}")
        elif section.empty_reason:
            parts.append(f"{section.section_type}: {section.empty_reason}")
    return "\n\n".join(parts).strip() or "No report content was produced."
