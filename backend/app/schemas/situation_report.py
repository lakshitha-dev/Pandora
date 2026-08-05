"""The Situation Report — the shape the whole product is about (API_CONTRACT §1.1).

Six *displayed* sections, but only three of them live in `sections`: priority,
sources, and confidence are the orchestrator's own fields (`priority`, the
top-level `citations` array, `confidence`). That keeps the six-section display
contract without duplicating data.

Also here: `InsufficientEvidence` (§1.4). An honest refusal is a **200 with a
report**, never an error — `has_sufficient_evidence: false` plus this object.
"""

from pydantic import BaseModel, Field

from app.schemas.common import (
    AssemblyMode,
    Confidence,
    OwningAgent,
    PriorityClass,
    SectionStatus,
    SectionType,
)

# The brief's mandated sentence. Rendered verbatim as the body's first line —
# do not reword, truncate, or template over it. Worth marks (SOLUTION.md §4.6).
INSUFFICIENT_EVIDENCE_MESSAGE = (
    "The available Pandora knowledge base does not contain sufficient "
    "evidence to answer this question."
)

INSUFFICIENT_EVIDENCE_BANNER = "⚠ Insufficient Evidence — Recommend Field Investigation"

# Fixed display order: priority 1 · species 2 · causes 3 · actions 4 · sources 5
# · confidence 6. Only the three content sections are ever rows in `sections`.
SECTION_DISPLAY_ORDER: dict[str, int] = {
    "affected_species": 2,
    "likely_causes": 3,
    "recommended_actions": 4,
}


class Priority(BaseModel):
    """Triage, from the corpus's own W1–W4 water incident scale (§4.5).

    `citation` is never null for a W-class — an uncited severity is an
    ungrounded model opinion, which is exactly what this system exists not to do.
    """

    class_: PriorityClass = Field(alias="class", serialization_alias="class")
    label: str
    reason: str
    citation: str | None = None
    page: int | None = None

    model_config = {"populate_by_name": True}


class ConfidenceBlock(BaseModel):
    level: Confidence
    reason: str
    groundedness: int = Field(ge=0, le=100)


class ReportSection(BaseModel):
    """One specialist-owned content section.

    Section independence is a hard guarantee: one section failing never blanks
    the others. `status != "filled"` is a normal path, not an edge case, and
    `empty_reason` is non-null whenever it applies.
    """

    section_type: SectionType
    owning_agent: OwningAgent
    status: SectionStatus
    empty_reason: str | None = None
    # Markdown. Inline citation markers are record IDs in brackets — `[INC-005]`,
    # `[FAU-003 p.13]` — not integers.
    content: str = ""
    claim_count: int = 0
    supported_claim_count: int = 0
    duration_ms: int = 0
    display_order: int = 0


class ConflictPosition(BaseModel):
    """One side of a disagreement, carrying its own reliability limitation."""

    record_id: str
    claim: str
    evidence_quality: str = ""
    reliability_limitation: str = ""


class Conflict(BaseModel):
    """Positions are presented side by side. No cause is declared.

    §14.3 of the corpus is a planted trap with a stated expected answer: show
    every position, name what limits each, decline to pick a winner.
    """

    record_ids: list[str] = Field(default_factory=list)
    conflict_nature: str = ""
    positions: list[ConflictPosition] = Field(default_factory=list)
    resolution_recommendation: str = ""


class SituationReport(BaseModel):
    priority: Priority
    # Drives the map — there is no separate endpoint. Empty = map stays idle.
    affected_region_ids: list[str] = Field(default_factory=list)
    assembly_mode: AssemblyMode = "sitrep"
    sections: list[ReportSection] = Field(default_factory=list)
    confidence: ConfidenceBlock
    conflicts: list[Conflict] = Field(default_factory=list)
    # True if any section timed out. A partial report is a success, not an error.
    was_partial: bool = False


class ClosestMatch(BaseModel):
    """A sub-threshold hit. Clearly labelled insufficient, never presented as an answer."""

    record_id: str
    title: str = ""
    relevance_score: float = 0.0
    page: int | None = None


class InsufficientEvidence(BaseModel):
    """§1.4. Non-null **only** when `has_sufficient_evidence` is false.

    The banner/body split is deliberate: the brief mandates a specific sentence,
    the command-center framing wants an actionable headline. Different slots, so
    neither is compromised.
    """

    banner: str = INSUFFICIENT_EVIDENCE_BANNER
    message: str = INSUFFICIENT_EVIDENCE_MESSAGE
    searched_scope: str = ""
    closest_matches: list[ClosestMatch] = Field(default_factory=list)
    what_would_resolve: str = ""
