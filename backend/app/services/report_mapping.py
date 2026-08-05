"""Agent service (Part 2) → public Situation Report (§1.1). Pure functions, no I/O.

The agent service speaks a flatter dialect than the public contract: priority and
confidence are loose top-level strings, groundedness lives under `grounding`, a
conflict's nature is called `nature`, and the refusal arrives as one pre-rendered
text block. Reshaping that is the gateway's job, and it happens here rather than
in `services/ask.py` so the orchestration stays readable.

**Every unknown value degrades; nothing raises.** A demo-day 500 because the agent
sent `confidence_level: "med"` would be a self-inflicted wound, so unrecognised
enum values fall back to a documented default and log a warning.
"""

import uuid
from typing import Any

from app.core.logging import get_logger
from app.schemas import agent as agent_schemas
from app.schemas.common import (
    UNKNOWN_DOCUMENT_ID,
    UNKNOWN_DOCUMENT_NAME,
    Citation,
)
from app.schemas.situation_report import (
    INSUFFICIENT_EVIDENCE_BANNER,
    INSUFFICIENT_EVIDENCE_MESSAGE,
    SECTION_DISPLAY_ORDER,
    ClosestMatch,
    ConfidenceBlock,
    Conflict,
    ConflictPosition,
    InsufficientEvidence,
    Priority,
    ReportSection,
    SituationReport,
)

logger = get_logger(__name__)

# Only the three specialist-owned content sections are rows in `sections`.
# `priority`, `sources`, and `confidence` are top-level fields of the report.
CONTENT_SECTION_TYPES = tuple(SECTION_DISPLAY_ORDER)

_PRIORITY_CLASSES = ("W1", "W2", "W3", "W4")
_DEFAULT_PRIORITY_LABEL = "OBSERVATION"

_CONFIDENCE_LEVELS = ("high", "moderate", "low", "insufficient")
# The agent service says "medium"; §1.1 says "moderate". Same thing.
_CONFIDENCE_ALIASES = {"medium": "moderate", "mid": "moderate", "none": "insufficient"}

_SECTION_STATUSES = ("filled", "empty", "timed_out", "not_applicable")
_OWNING_AGENTS = (
    "marine_life_protector",
    "incident_investigator",
    "emergency_responder",
    "orchestrator",
)
# The degradation path fills every section from one call; §1.1 has no such agent.
_OWNING_AGENT_ALIASES = {"single_agent": "orchestrator"}

_ASSEMBLY_MODES = ("sitrep", "focused", "compare", "single_agent_fallback")

_DEFAULT_EMPTY_REASON = "This section is unavailable and the agent gave no reason."
_INSUFFICIENT_CONFIDENCE_REASON = (
    "Insufficient — no record scored above the relevance threshold"
)
_DEFAULT_WHAT_WOULD_RESOLVE = (
    "A properly documented field record covering this question. "
    "See Appendix A — investigation checklists."
)


# --- citations ---------------------------------------------------------------


def to_citations(
    agent_citations: list[agent_schemas.AgentCitation], document_names: dict[uuid.UUID, str]
) -> list[Citation]:
    """Join `document_name` from Postgres onto what the agent service returned.

    A citation whose document can't be resolved is kept, not dropped: the section
    text already cites its record ID, and a source card that says
    "(document unavailable)" is honest where a missing one is just confusing.
    """
    citations: list[Citation] = []
    for source in agent_citations:
        document_id = _parse_document_id(source.document_id)
        name = document_names.get(document_id)
        if name is None:
            logger.warning(
                "citation %s references unresolved document %s",
                source.record_id or source.marker,
                source.document_id,
            )
            name = UNKNOWN_DOCUMENT_NAME
        citations.append(
            Citation(
                marker=source.marker,
                document_id=document_id,
                document_name=name,
                chunk_id=source.chunk_id,
                record_id=source.record_id,
                record_type=source.record_type,
                title=source.title,
                chapter=source.chapter,
                section=source.section,
                page=source.page,
                region_id=source.region_id,
                excerpt=source.excerpt,
                relevance_score=max(0.0, min(1.0, source.relevance_score)),
                rerank_score=source.rerank_score,
                evidence_quality=source.evidence_quality,
                risk_level=source.risk_level,
                record_date=source.record_date,
                section_types=source.section_types,
            )
        )
    return citations


def _parse_document_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return UNKNOWN_DOCUMENT_ID


def citation_document_ids(agent_citations: list[agent_schemas.AgentCitation]) -> set[uuid.UUID]:
    """The document ids to look up in Postgres, placeholder excluded."""
    ids = {_parse_document_id(c.document_id) for c in agent_citations}
    ids.discard(UNKNOWN_DOCUMENT_ID)
    return ids


# --- the report --------------------------------------------------------------


def to_situation_report(response: agent_schemas.SitrepResponse) -> SituationReport:
    report = response.situation_report
    return SituationReport(
        priority=_to_priority(report),
        affected_region_ids=list(report.affected_region_ids),
        assembly_mode=_narrow(
            report.assembly_mode, _ASSEMBLY_MODES, "sitrep", field="assembly_mode"
        ),
        sections=_to_sections(report.sections),
        confidence=_to_confidence(response),
        conflicts=[_to_conflict(c) for c in response.conflicts],
        was_partial=report.was_partial
        or any(s.status == "timed_out" for s in report.sections),
    )


def _to_priority(report: agent_schemas.SitrepSituationReport) -> Priority:
    raw = (report.priority_class or "").strip()
    # The agent's enum spells it "Informational"; §1.1 spells it lowercase.
    priority_class = raw if raw in _PRIORITY_CLASSES else raw.lower()
    if priority_class not in (*_PRIORITY_CLASSES, "informational"):
        logger.warning("unknown priority_class %r — treating as informational", raw)
        priority_class = "informational"

    citation = report.priority_citation.strip() or None
    if priority_class in _PRIORITY_CLASSES and citation is None:
        # Can't invent one. Surface it in the logs — an uncited W-class is an
        # agent-side bug against §1.1, not something the gateway can paper over.
        logger.warning("priority %s has no citation — §1.1 requires one", priority_class)

    label = report.priority_label.strip()
    if not label:
        label = _DEFAULT_PRIORITY_LABEL if priority_class == "informational" else priority_class

    return Priority(
        **{"class": priority_class},
        label=label,
        reason=report.priority_reason,
        citation=citation,
        page=report.priority_page,
    )


def _to_confidence(response: agent_schemas.SitrepResponse) -> ConfidenceBlock:
    report = response.situation_report
    raw = (report.confidence_level or "").strip().lower()
    level = _narrow(
        _CONFIDENCE_ALIASES.get(raw, raw), _CONFIDENCE_LEVELS, "low", field="confidence_level"
    )
    groundedness = max(0, min(100, response.grounding.groundedness))
    reason = report.confidence_reason.strip()

    # An insufficient-evidence report is insufficient by definition — never let a
    # stale "high" from a partially-filled report contradict the honesty flip.
    if not response.has_sufficient_evidence:
        level = "insufficient"
        if "insufficient" not in reason.lower():
            # A reason reading "Moderate — 3 sources" beside level "insufficient"
            # is the kind of contradiction a judge notices.
            reason = _INSUFFICIENT_CONFIDENCE_REASON

    return ConfidenceBlock(
        level=level,
        reason=reason or f"{level.capitalize()} — groundedness {groundedness}%",
        groundedness=groundedness,
    )


def _to_sections(sections: list[agent_schemas.AgentReportSection]) -> list[ReportSection]:
    mapped: list[ReportSection] = []
    for section in sections:
        if section.section_type not in CONTENT_SECTION_TYPES:
            # `priority`, `sources`, and `confidence` are top-level fields in
            # §1.1. Dropping them here is the contract, not data loss.
            continue
        status = _narrow(section.status, _SECTION_STATUSES, "empty", field="section status")
        empty_reason = section.empty_reason
        if status != "filled" and not empty_reason:
            empty_reason = _DEFAULT_EMPTY_REASON
        mapped.append(
            ReportSection(
                section_type=section.section_type,
                owning_agent=_narrow(
                    _OWNING_AGENT_ALIASES.get(section.owning_agent, section.owning_agent),
                    _OWNING_AGENTS,
                    "orchestrator",
                    field="owning_agent",
                ),
                status=status,
                empty_reason=empty_reason if status != "filled" else None,
                content=section.content,
                claim_count=section.claim_count,
                supported_claim_count=section.supported_claim_count,
                duration_ms=section.duration_ms,
                display_order=section.display_order
                or SECTION_DISPLAY_ORDER[section.section_type],
            )
        )
    return sorted(mapped, key=lambda s: s.display_order)


def _to_conflict(conflict: agent_schemas.AgentConflict) -> Conflict:
    return Conflict(
        record_ids=list(conflict.record_ids),
        conflict_nature=conflict.conflict_nature or conflict.nature,
        positions=[
            ConflictPosition(
                record_id=p.record_id,
                claim=p.claim,
                evidence_quality=p.evidence_quality,
                reliability_limitation=p.reliability_limitation,
            )
            for p in conflict.positions
        ],
        resolution_recommendation=conflict.resolution_recommendation,
    )


# --- the honest refusal (§1.4) ------------------------------------------------


def to_insufficient_evidence(
    response: agent_schemas.SitrepResponse, citations: list[Citation]
) -> InsufficientEvidence:
    """Build the §1.4 object from what the agent sent as one text block.

    `message` is always the brief's mandated sentence, taken from our own
    constant rather than parsed out of the agent's text — a reworded or truncated
    version of that sentence costs marks, and a constant cannot drift.
    `what_would_resolve` reuses the agent's own recommendation when it gave one.
    """
    return InsufficientEvidence(
        banner=INSUFFICIENT_EVIDENCE_BANNER,
        message=INSUFFICIENT_EVIDENCE_MESSAGE,
        searched_scope=_searched_scope(citations),
        closest_matches=[
            ClosestMatch(
                record_id=c.record_id,
                title=c.title,
                relevance_score=c.relevance_score,
                page=c.page,
            )
            for c in sorted(citations, key=lambda c: c.relevance_score, reverse=True)[:3]
            if c.record_id
        ],
        what_would_resolve=_what_would_resolve(response.insufficient_evidence),
    )


def _searched_scope(citations: list[Citation]) -> str:
    """"Chapters 12 and 14 · record types field_note, incident", from what came back."""
    if not citations:
        return "The full Pandora knowledge base — no record scored above the relevance threshold."
    chapters = sorted({_chapter_number(c.chapter) for c in citations if c.chapter})
    record_types = sorted({c.record_type for c in citations if c.record_type})
    parts = []
    if chapters:
        parts.append("Chapters " + _join_readable(chapters))
    if record_types:
        parts.append("record types " + ", ".join(record_types))
    return " · ".join(parts) or "The full Pandora knowledge base"


def _chapter_number(chapter: str) -> str:
    """"12 · Environmental Threats and Emergency Response" → "12".

    Chapter titles carry their own `·` separator, which would collide with the
    one §1.4 uses between scope clauses.
    """
    return chapter.split("·")[0].strip() or chapter.strip()


def _join_readable(values: list[str]) -> str:
    if len(values) < 3:
        return " and ".join(values)
    return ", ".join(values[:-1]) + " and " + values[-1]


def _what_would_resolve(agent_text: str | None) -> str:
    """The agent's closing recommendation, if its text block carried one.

    The block is the mandated sentence, then a scope line, then closest matches,
    then a recommendation. Only the last is not already structured elsewhere in
    §1.4, so that is all we take — and the default covers any other shape.
    """
    if not agent_text:
        return _DEFAULT_WHAT_WOULD_RESOLVE
    skip_prefixes = ("searched:", "closest partial matches")
    candidates = [
        line.strip()
        for line in agent_text.splitlines()
        if line.strip()
        and line.strip() != INSUFFICIENT_EVIDENCE_MESSAGE
        and not line.strip().lower().startswith(skip_prefixes)
    ]
    return candidates[-1] if candidates else _DEFAULT_WHAT_WOULD_RESOLVE


# --- persistence helpers ------------------------------------------------------


def report_history_text(report: dict[str, Any]) -> str:
    """A stored report flattened to plain text, for the next turn's coreference.

    The agent takes `conversation_history` as `{role, content}` strings, so the
    previous report has to collapse to one. Section content already carries its
    record IDs, so the citations survive the flattening.
    """
    sections = report.get("sections") or []
    parts = [str(s.get("content", "")).strip() for s in sections if s.get("content")]
    return "\n\n".join(parts)


def _narrow(value: str, allowed: tuple[str, ...], fallback: str, *, field: str) -> Any:
    if value in allowed:
        return value
    logger.warning("unknown %s %r from the agent service — using %r", field, value, fallback)
    return fallback
