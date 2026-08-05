"""Pandora-shaped fixtures for `AGENT_STUB_MODE=true`.

These are the contract's own examples (§1.1 for the grounded path, §1.4 for the
honest refusal), so the gateway and the frontend can be integrated — and demoed —
without the agent service or Azure being reachable.

The refusal branch matters as much as the grounded one: a client that has only
ever seen a successful report will not have built the honesty-flip state, which
is a 20-mark criterion.
"""

import json
import uuid
from collections.abc import Iterator

from app.db.models import CORPUS_DOCUMENT_SLUG
from app.schemas.agent import (
    RagIncident,
    RagIncidentListResponse,
    RagIngestResponse,
    RagQueryRequest,
    RagQueryResponse,
    SitrepRequest,
    SitrepResponse,
)

# Kept identical to the agent's own INSUFFICIENT_EVIDENCE_MESSAGE. It is the
# brief's mandated sentence — if these two ever drift, the stub is wrong.
INSUFFICIENT_EVIDENCE_MESSAGE = (
    "The available Pandora knowledge base does not contain sufficient "
    "evidence to answer this question."
)

_INCIDENT_WORDS = (
    "water", "turquoise", "fish", "reef", "awa", "plume", "vent", "bloom",
    "species", "incident", "spill", "shellfish", "colour", "color",
)


def _is_in_corpus(question: str) -> bool:
    """Crude on-corpus check so the stub can exercise both branches."""
    lowered = question.lower()
    return any(word in lowered for word in _INCIDENT_WORDS)


def _citations() -> list[dict]:
    return [
        {
            "marker": 1,
            "document_id": CORPUS_DOCUMENT_SLUG,
            "chunk_id": "pandora-chunk-0031",
            "record_id": "INC-001",
            "record_type": "incident",
            "title": "Turquoise Water Event",
            "chapter": "12 · Environmental Threats and Emergency Response",
            "section": "Plausible causes",
            "page": 40,
            "region_id": "REG-01",
            "excerpt": (
                "Plausible causes include mineral sediment, plankton bloom, chemical "
                "release, or light reflection. No single cause has been confirmed."
            ),
            "relevance_score": 0.94,
            "rerank_score": 9.4,
            "evidence_quality": "provisional_interpretation",
            "risk_level": "high",
            "record_date": None,
        },
        {
            "marker": 2,
            "document_id": CORPUS_DOCUMENT_SLUG,
            "chunk_id": "pandora-chunk-0164",
            "record_id": "LAB-C",
            "record_type": "field_note",
            "title": "Laboratory Note LAB-C",
            "chapter": "14 · Monitoring Data",
            "section": "14.3 Conflicting Field Notes",
            "page": 47,
            "region_id": "REG-01",
            "excerpt": (
                "Detected elevated harmless carbonate particles and moderate plankton "
                "density, but the sample chain-of-custody form was incomplete."
            ),
            "relevance_score": 0.88,
            "rerank_score": 8.8,
            "evidence_quality": "disputed_report",
            "risk_level": None,
            "record_date": "2026-06-05",
        },
    ]


def _conflicts() -> list[dict]:
    """§14.3 is a planted trap with a stated expected answer: three positions,
    each with its own limitation, and no cause declared."""
    return [
        {
            "record_ids": ["FN-A", "FN-B", "LAB-C"],
            "nature": (
                "Three records propose incompatible causes for the same colour "
                "change at Awa Reef."
            ),
            "reliability_limitation": "No record resolves the others.",
            "positions": [
                {
                    "record_id": "FN-A",
                    "claim": "Plankton bloom; began after three calm hot days; no chemical odor.",
                    "evidence_quality": "disputed_report",
                    "reliability_limitation": "Interpretation only; no chemical sampling performed.",
                },
                {
                    "record_id": "FN-B",
                    "claim": "Upstream pigment workshop maintenance; damaged waste container observed.",
                    "evidence_quality": "disputed_report",
                    "reliability_limitation": "Entry of material into the water was never confirmed.",
                },
                {
                    "record_id": "LAB-C",
                    "claim": "Elevated harmless carbonate particles and moderate plankton density.",
                    "evidence_quality": "disputed_report",
                    "reliability_limitation": "Sample chain-of-custody form incomplete.",
                },
            ],
            "resolution_recommendation": (
                "Documented resampling per checklist A.1 — Water Investigation."
            ),
        }
    ]


def _grounded_sections() -> list[dict]:
    return [
        {
            "section_type": "affected_species",
            "owning_agent": "marine_life_protector",
            "status": "filled",
            "empty_reason": None,
            "content": (
                "**FAU-001 Tideglass Grazer** — juveniles are documented as vulnerable to "
                "turbidity in shallow shelf habitat [FAU-001]. **FAU-002 Ribbonfin Skimmer** "
                "— recorded as sensitive to surface oil films [FAU-002]."
            ),
            "claim_count": 2,
            "supported_claim_count": 2,
            "duration_ms": 2610,
            "display_order": 2,
        },
        {
            "section_type": "likely_causes",
            "owning_agent": "incident_investigator",
            "status": "filled",
            "empty_reason": None,
            "content": (
                "**No cause is established.** Three records make incompatible claims about "
                "this event and the corpus does not resolve them [FN-A] [FN-B] [LAB-C]. "
                "`INC-001` lists four plausible causes without confirming any [INC-001]."
            ),
            "claim_count": 3,
            "supported_claim_count": 3,
            "duration_ms": 3180,
            "display_order": 3,
        },
        {
            "section_type": "recommended_actions",
            "owning_agent": "emergency_responder",
            "status": "filled",
            "empty_reason": None,
            "content": (
                "1. Record observations and collect samples upstream and downstream "
                "[INC-001].\n2. Restrict sensitive water use pending results [REG-01].\n"
                "3. Issue a public update naming the cause as **not yet confirmed** [POL-010]."
            ),
            "claim_count": 3,
            "supported_claim_count": 3,
            "duration_ms": 2890,
            "display_order": 4,
        },
    ]


def _grounding() -> dict:
    return {
        "groundedness": 96,
        "rules": [
            {"number": n, "name": name, "passed": True, "detail": "ok"}
            for n, name in enumerate(
                [
                    "Closed book",
                    "Every claim cited",
                    "No merged species",
                    "Evidence labels preserved",
                    "Conflicts presented, not resolved",
                    "No invented record IDs",
                    "Refuse when thin",
                    "No real-world facts",
                ],
                start=1,
            )
        ],
        "unsupported_sentences": [],
    }


def _grounded_sitrep() -> dict:
    return {
        "situation_report": {
            "priority_class": "W3",
            "priority_reason": (
                "Fish avoidance and water discolouration with offshore movement reported."
            ),
            "priority_citation": "§4.5 Water Incident Classification",
            "priority_label": "EMERGENCY",
            "priority_page": 12,
            "affected_region_ids": ["REG-01"],
            "assembly_mode": "sitrep",
            "confidence_level": "medium",
            "confidence_reason": (
                "Moderate — 3 sources, 1 unresolved conflict, chain of custody incomplete"
            ),
            "was_partial": False,
            "sections": _grounded_sections(),
        },
        "citations": _citations(),
        "grounding": _grounding(),
        "conflicts": _conflicts(),
        "has_sufficient_evidence": True,
        "insufficient_evidence": None,
        "llm_call_count": 6,
        "duration_ms": 5240,
        "top_rerank_score": 9.4,
    }


def _refused_sitrep() -> dict:
    return {
        "situation_report": {
            "priority_class": "Informational",
            "priority_reason": "No incident indicators detected in the available evidence.",
            "priority_citation": "",
            "priority_label": "OBSERVATION",
            "priority_page": None,
            "affected_region_ids": [],
            "assembly_mode": "sitrep",
            "confidence_level": "insufficient",
            "confidence_reason": "Insufficient — no record scored above the relevance threshold",
            "was_partial": False,
            "sections": [
                {
                    "section_type": "affected_species",
                    "owning_agent": "marine_life_protector",
                    "status": "empty",
                    "empty_reason": "No species records matched this query.",
                    "content": "",
                    "claim_count": 0,
                    "supported_claim_count": 0,
                    "duration_ms": 420,
                    "display_order": 2,
                }
            ],
        },
        "citations": [],
        "grounding": {"groundedness": 0, "rules": [], "unsupported_sentences": []},
        "conflicts": [],
        "has_sufficient_evidence": False,
        "insufficient_evidence": {
            "banner": "⚠ Insufficient Evidence — Recommend Field Investigation",
            "message": INSUFFICIENT_EVIDENCE_MESSAGE,
            "searched_scope": "record types: fauna, monitoring",
            "closest_matches": [
                {
                    "record_id": "SV-105",
                    "title": "Deep Current Expanse acoustic survey",
                    "relevance_score": 0.41,
                    "page": 47,
                }
            ],
            "what_would_resolve": (
                "An acoustic survey record for this species in this region. "
                "See checklist A.2 — Wildlife Emergency."
            ),
        },
        "llm_call_count": 2,
        "duration_ms": 1840,
        "top_rerank_score": 4.1,
    }


# --- public fixture entry points ---------------------------------------------


def ingest(document_id: uuid.UUID) -> RagIngestResponse:
    return RagIngestResponse(
        document_id=str(document_id),
        status="indexed",
        chunk_count=23,
        record_count=0,
        page_count=9,
        chunking_mode="narrative",
        error_message=None,
        duration_ms=4210,
    )


def sitrep(request: SitrepRequest) -> SitrepResponse:
    payload = _grounded_sitrep() if _is_in_corpus(request.question) else _refused_sitrep()
    return SitrepResponse.model_validate(payload)


def query(request: RagQueryRequest) -> RagQueryResponse:
    payload = _grounded_sitrep() if _is_in_corpus(request.question) else _refused_sitrep()
    return RagQueryResponse.model_validate(
        {
            "sections": payload["situation_report"]["sections"],
            "citations": payload["citations"],
            "grounding": payload["grounding"],
            "conflicts": payload["conflicts"],
            "has_sufficient_evidence": payload["has_sufficient_evidence"],
            "retrieved_chunk_count": len(payload["citations"]),
            "top_rerank_score": payload["top_rerank_score"],
            "rerank_mode": "none",
            "duration_ms": payload["duration_ms"],
        }
    )


def incidents(*, limit: int = 50, offset: int = 0) -> RagIncidentListResponse:
    rows = [
        RagIncident(
            record_id="INC-005",
            title="Vent Plume Release",
            region_id="REG-05",
            region_name="Obsidian Reach",
            risk_level="critical",
            chapter="12 · Environmental Threats and Emergency Response",
            page=42,
            summary_excerpt=(
                "Yellow plume observed at the vent edge with dead shellfish along "
                "the black-sand coast."
            ),
            evidence_quality="verified_observation",
        ),
        RagIncident(
            record_id="INC-001",
            title="Turquoise Water Event",
            region_id="REG-01",
            region_name="Luminous Shelf",
            risk_level="high",
            chapter="12 · Environmental Threats and Emergency Response",
            page=40,
            summary_excerpt=(
                "Water colour shifted to turquoise over three days; fish moved offshore."
            ),
            evidence_quality="provisional_interpretation",
        ),
    ]
    return RagIncidentListResponse(
        incidents=rows[offset : offset + limit], total=len(rows), limit=limit, offset=offset
    )


def error_frame(code: str, message: str) -> str:
    return json.dumps(
        {
            "step_type": "error",
            "sequence_number": 0,
            "duration_ms": 0,
            "payload": {"code": code, "message": message},
        }
    )


def sitrep_stream(request: SitrepRequest) -> Iterator[tuple[str, str]]:
    """A trace with the same event vocabulary and ordering as the real one.

    Priority and the map zone come early on purpose — they drive the triage
    banner and the map, and a stub that emitted them last would let a client
    ship an ordering bug that only shows up against the live agent.
    """
    grounded = _is_in_corpus(request.question)
    payload = _grounded_sitrep() if grounded else _refused_sitrep()
    report = payload["situation_report"]

    steps: list[tuple[str, dict]] = [
        ("query.received", {"question": request.question}),
        (
            "query.classified",
            {
                "use_case": "emergency_response",
                "severity_class": report["priority_class"],
                "query_shape": "sitrep",
            },
        ),
        (
            "priority.classified",
            {
                "class": report["priority_class"],
                "label": report["priority_label"],
                "reason": report["priority_reason"],
                "citation": report["priority_citation"] or None,
                "page": report["priority_page"],
            },
        ),
        (
            "map.zone_lit",
            {
                "region_ids": report["affected_region_ids"],
                "priority_class": report["priority_class"],
            },
        ),
        (
            "route.decided",
            {
                "mode": "sitrep",
                "specialists": [s["owning_agent"] for s in report["sections"]],
                "reason": "Incident indicators detected → sitrep mode",
            },
        ),
        ("retrieval.started", {"agent": "orchestrator", "filters": {}, "k": 30}),
        (
            "retrieval.completed",
            {
                "candidate_count": 38,
                "kept_count": len(payload["citations"]),
                "top_rerank_score": payload["top_rerank_score"],
            },
        ),
    ]

    for section in report["sections"]:
        steps.append(
            ("section.filling", {
                "section_type": section["section_type"],
                "owning_agent": section["owning_agent"],
            })
        )
        if section["status"] == "filled":
            steps.append(
                ("section.completed", {
                    "section_type": section["section_type"],
                    "claim_count": section["claim_count"],
                    "source_count": len(payload["citations"]),
                    "duration_ms": section["duration_ms"],
                })
            )
        else:
            steps.append(
                ("section.unavailable", {
                    "section_type": section["section_type"],
                    "empty_reason": section["empty_reason"],
                })
            )

    for conflict in payload["conflicts"]:
        steps.append(
            ("conflict.detected", {
                "record_ids": conflict["record_ids"],
                "conflict_nature": conflict["nature"],
            })
        )

    steps.append(("validation.running", {"rule_count": 8}))
    steps.append(
        ("validation.result", {
            "rules": payload["grounding"]["rules"],
            "groundedness": payload["grounding"]["groundedness"],
        })
    )
    # The terminal frame carries the complete report so a client can use the
    # stream alone and never call POST /api/v1/ask.
    steps.append(("answer.completed", payload))

    for sequence, (step_type, step_payload) in enumerate(steps, start=1):
        yield (
            step_type,
            json.dumps(
                {
                    "step_type": step_type,
                    "sequence_number": sequence,
                    "duration_ms": 0,
                    "payload": step_payload,
                }
            ),
        )
