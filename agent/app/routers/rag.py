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

from fastapi import APIRouter, HTTPException

from app.chains.generation import INSUFFICIENT_EVIDENCE_MESSAGE
from app.chains.section_fill import fill_section, rewrite_with_history
from app.core.llm import LLMError, embed_texts
from app.ingestion.extract import UnsupportedFileType, chunk_uploaded, extract_text
from app.ingestion.search_index import chunk_to_document, upload
from app.models.schemas import (
    Citation,
    Grounding,
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
            merged_rules.append(failed[0] if failed else per[0])
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
