"""POST /rag/ingest and POST /rag/query — the Layer 1 core RAG endpoints.

Layers 1 and 2 use /rag/query directly with no orchestrator. It is also
degradation rung 3: when the agentic layer fails, the orchestrator falls back
here with section_type=None and produces a structurally identical report.

Section-fill logic itself lives in app/chains/section_fill.py, shared with
the specialist agents (app/agents/specialists.py) so both callers run the
exact same retrieve → generate → GroundingGate pipeline.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Query

from app.chains.generation import INSUFFICIENT_EVIDENCE_MESSAGE
from app.chains.section_fill import fill_section, rewrite_with_history
from app.core.llm import LLMError, embed_texts
from app.ingestion.extract import UnsupportedFileType, chunk_uploaded, extract_text
from app.ingestion.search_index import (
    chunk_to_document,
    delete_by_document_id,
    list_by_record_type,
    upload,
)
from app.models.schemas import (
    Citation,
    Grounding,
    Incident,
    IncidentListResponse,
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    ReportSection,
    SectionStatus,
    SectionType,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["rag"])


# ─────────────────────────────────────────────────────────────────────────
# POST /rag/ingest
# ─────────────────────────────────────────────────────────────────────────


@router.post("/rag/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest) -> IngestResponse:
    """Extract, chunk, embed, and index an uploaded document."""
    started = time.perf_counter()

    try:
        doc = extract_text(req.content_base64, req.file_name, req.content_type)
    except UnsupportedFileType as exc:
        raise HTTPException(status_code=400, detail={
            "error": {"code": "unsupported_file_type", "message": str(exc)}
        }) from exc
    except ValueError as exc:
        return IngestResponse(
            document_id=req.document_id, status="failed", error_message=str(exc),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    try:
        chunks, mode, record_count = chunk_uploaded(doc.text, req.document_id, req.file_name)
        if not chunks:
            raise ValueError("document produced no indexable chunks")

        vectors = embed_texts(c.content for c in chunks)
        upload([chunk_to_document(c, v) for c, v in zip(chunks, vectors)])
    except Exception as exc:  # noqa: BLE001
        logger.exception("ingest failed for %s", req.file_name)
        return IngestResponse(
            document_id=req.document_id, status="failed",
            error_message=str(exc)[:400],
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    logger.info("ingested %s: %d chunks (%s)", req.file_name, len(chunks), mode)
    return IngestResponse(
        document_id=req.document_id,
        status="indexed",
        chunk_count=len(chunks),
        record_count=record_count,
        page_count=doc.page_count,
        chunking_mode=mode,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


# ─────────────────────────────────────────────────────────────────────────
# POST /rag/query
# ─────────────────────────────────────────────────────────────────────────


@router.post("/rag/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    """Retrieval + grounded generation for one section, or a plain answer.

    Two modes, deliberately different:

      section_type set  -> fill that one Situation Report section, using its
                           record-type filter and its section instruction.
                           This is what the orchestrator dispatches (Layer 5).

      section_type null -> a plain grounded answer over unfiltered retrieval.
                           This is Layer 1 — "ingest -> retrieve -> grounded
                           cited answer" — and it is also degradation rung 3,
                           the fallback when the agentic layer fails.

    Forcing a general question ("which accommodations are safest in storm
    season?") through the likely_causes profile starves retrieval and
    produces a bad answer. Layer 1 must not do that.
    """
    started = time.perf_counter()
    question = rewrite_with_history(req.question, req.conversation_history)

    targets = [req.section_type] if req.section_type else [None]

    sections: list[ReportSection] = []
    all_chunks: list = []
    gates: list = []
    answers: list = []

    for section in targets:
        try:
            result = fill_section(section, question, req=req)
        except LLMError as exc:
            logger.warning("section %s failed: %s", section, exc)
            result = None
            sections.append(
                ReportSection(
                    section_type=section or SectionType.LIKELY_CAUSES,
                    status=SectionStatus.EMPTY,
                    empty_reason=f"generation failed: {exc}",
                )
            )
            continue

        sections.append(result.section)
        all_chunks.extend(result.chunks)
        if result.answer:
            answers.append(result.answer)
            # A refused section has an answer but no gate — there is nothing
            # to validate when nothing was retrieved. Only real gates merge.
            if result.gate is not None:
                gates.append(result.gate)

    # ── merge evidence across sections ───────────────────────────────────
    cited_ids: list[str] = []
    for a in answers:
        for rid in a.cited_record_ids:
            if rid not in cited_ids:
                cited_ids.append(rid)

    by_id = {}
    for c in all_chunks:
        by_id.setdefault(c.citation_id, c)

    citations = [
        Citation(**{**by_id[rid].to_citation(i + 1),
                    "record_type": by_id[rid].record_type,
                    "rerank_score": by_id[rid].rerank_score})
        for i, rid in enumerate(cited_ids)
        if rid in by_id
    ]

    # Merge grounding: worst-case pass across sections, mean groundedness.
    if gates:
        merged_rules = []
        for number in range(1, 9):
            per = [g.rules[number - 1] for g in gates]
            failed = [r for r in per if not r.passed]
            if failed:
                merged_rules.append(failed[0])
                continue
            # Prefer a section that actually evaluated the rule over one that
            # reported "not engaged" — see the note in orchestrator._merge_grounding.
            engaged = [r for r in per if "not engaged" not in r.detail]
            merged_rules.append(engaged[0] if engaged else per[0])
        grounding = Grounding(
            groundedness=round(sum(g.groundedness for g in gates) / len(gates)),
            rules=merged_rules,
            unsupported_sentences=[s for g in gates for s in g.unsupported_sentences],
        )
        conflicts = [c for g in gates for c in g.conflicts]
        seen_sets: set[tuple[str, ...]] = set()
        unique_conflicts = []
        for c in conflicts:
            key = tuple(sorted(c.record_ids))
            if key not in seen_sets:
                seen_sets.add(key)
                unique_conflicts.append(c)
        conflicts = unique_conflicts
    else:
        grounding = Grounding(groundedness=0, rules=[], unsupported_sentences=[])
        conflicts = []

    top_score = max((c.normalised_score for c in all_chunks), default=0.0) * 10.0
    sufficient = bool(cited_ids) and any(
        s.status == SectionStatus.FILLED for s in sections
    )

    if not sufficient:
        for s in sections:
            if not s.content:
                s.content = INSUFFICIENT_EVIDENCE_MESSAGE

    return QueryResponse(
        sections=sections,
        citations=citations,
        grounding=grounding,
        conflicts=conflicts,
        has_sufficient_evidence=sufficient,
        retrieved_chunk_count=len(by_id),
        top_rerank_score=round(top_score, 2),
        rerank_mode="none",
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


# ─────────────────────────────────────────────────────────────────────────
# GET /rag/incidents — the incident register (API_CONTRACT §1.6)
# ─────────────────────────────────────────────────────────────────────────

_INCIDENT_FIELDS = [
    "record_id",
    "title",
    "region_id",
    "risk_level",
    "chapter",
    "page",
    "content",
    "evidence_quality",
]

# The index carries region_id but not the region's display name, so it is
# resolved from the region records themselves. The corpus is pre-indexed and
# immutable during a run, so one lookup per process is enough.
_region_names: dict[str, str] | None = None


def _region_name_map() -> dict[str, str]:
    global _region_names
    if _region_names is None:
        try:
            rows, _ = list_by_record_type(
                "region", limit=100, select=["record_id", "region_id", "title"]
            )
        except Exception:  # noqa: BLE001 - a missing name must not fail the listing
            logger.warning("region name lookup failed", exc_info=True)
            return {}
        _region_names = {
            (r.get("region_id") or r.get("record_id") or ""): (r.get("title") or "")
            for r in rows
        }
        _region_names.pop("", None)
    return _region_names


def _summary_excerpt(content: str, limit: int = 240) -> str:
    """First prose line of the record, headings and metadata brackets stripped."""
    body = "\n".join(
        ln for ln in (content or "").splitlines() if not ln.lstrip().startswith(("#", "["))
    ).strip()
    body = " ".join(body.split())
    return body[:limit] + ("…" if len(body) > limit else "")


@router.get("/rag/incidents", response_model=IncidentListResponse)
def incidents(
    risk_level: str | None = Query(default=None),
    region_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> IncidentListResponse:
    """Filtered projection of incident metadata already in the index.

    No retrieval work and no LLM call — §1.6 backs a register screen, not a
    question. Selecting a row pre-fills the Command Center question box.
    """
    try:
        rows, total = list_by_record_type(
            "incident",
            risk_level=risk_level,
            region_id=region_id,
            limit=limit,
            offset=offset,
            select=_INCIDENT_FIELDS,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("incident listing failed")
        raise HTTPException(status_code=502, detail={
            "error": {"code": "search_unavailable", "message": str(exc)[:300]}
        }) from exc

    names = _region_name_map()
    incidents_out = [
        Incident(
            record_id=r.get("record_id") or "",
            title=r.get("title") or "",
            region_id=r.get("region_id") or None,
            region_name=names.get(r.get("region_id") or ""),
            risk_level=r.get("risk_level") or None,
            chapter=r.get("chapter") or "",
            page=r.get("page"),
            summary_excerpt=_summary_excerpt(r.get("content") or ""),
            evidence_quality=r.get("evidence_quality") or "",
        )
        for r in rows
    ]
    return IncidentListResponse(
        incidents=incidents_out, total=total, limit=limit, offset=offset
    )


# ─────────────────────────────────────────────────────────────────────────
# DELETE /rag/documents/{document_id}
# ─────────────────────────────────────────────────────────────────────────


@router.delete("/rag/documents/{document_id}", status_code=204)
def delete_document(document_id: str) -> None:
    """Drop a document's vectors so the gateway's delete doesn't orphan them.

    Idempotent: deleting a document with no chunks is a 204, not a 404. The
    gateway calls this before removing its own row, and a retry must not fail.
    """
    try:
        delete_by_document_id(document_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("vector delete failed for %s", document_id)
        raise HTTPException(status_code=502, detail={
            "error": {"code": "search_unavailable", "message": str(exc)[:300]}
        }) from exc
