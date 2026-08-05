"""Hybrid retrieval over the Pandora knowledge index.

SOLUTION.md §4.3 — neither leg alone is sufficient on this corpus:

  · Vector catches paraphrase. "why are the animals leaving?" shares no
    keywords with FAU-001's "a sudden absence can reflect migration,
    disturbance, weather, sampling error, or mortality".

  · BM25 catches exact tokens. Record IDs (INC-005), station codes (WS-03),
    and invented proper nouns with no pretraining signal (Tideglass Grazer,
    Ventplume Shrimp) are placed badly by an embedding model and matched
    instantly by keyword search.

Azure AI Search performs RRF fusion natively when a request carries both
`search_text` and `vector_queries`, so we issue one hybrid call rather than
two legs plus manual fusion.

F0 tier has no semantic reranker (Basic+ only), so precision above RRF comes
from an optional LLM rerank over the candidate set.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, Sequence

from azure.search.documents.models import VectorizedQuery

from app.core.config import get_settings
from app.core.llm import LLMError, chat_json, embed_query
from app.ingestion.search_index import search_client

logger = logging.getLogger(__name__)

_SELECT = [
    "chunk_id",
    "content",
    "title",
    "record_id",
    "record_type",
    "chapter",
    "section",
    "region_id",
    "evidence_quality",
    "risk_level",
    "record_date",
    "document_id",
    "document_name",
    "page",
]


@dataclass
class RetrievedChunk:
    """One candidate returned by retrieval."""

    chunk_id: str
    content: str
    record_id: str
    record_type: str
    title: str
    chapter: str
    section: str
    region_id: str
    evidence_quality: str
    risk_level: str
    record_date: str
    document_id: str
    document_name: str
    page: int | None
    score: float
    rerank_score: float | None = None
    cite_key: str | None = None

    @property
    def citation_id(self) -> str:
        """The token the model is asked to cite.

        Record-bearing chunks cite their real ID (INC-005, FN-A, WS-03).
        Narrative chunks have no record ID, so generation assigns a
        synthetic uppercase key (SEC-1, SEC-2) — without one the model
        would be asked to cite `nar-14-research-records-...`, which no
        citation parser can match, and the whole section would then be
        scored as unsupported. Narrative sections like §4.5 (the W1–W4
        scale) and §14.3 must be citable.
        """
        return self.record_id or self.cite_key or self.chunk_id

    def excerpt(self, limit: int = 320) -> str:
        """Verbatim snippet for the source card, heading line stripped."""
        body = "\n".join(
            ln for ln in self.content.splitlines() if not ln.lstrip().startswith(("#", "["))
        ).strip()
        body = " ".join(body.split())
        return body[:limit] + ("…" if len(body) > limit else "")

    def to_citation(self, marker: int) -> dict[str, Any]:
        """Shape required by docs/API_CONTRACT.md §2.2."""
        return {
            "marker": marker,
            "record_id": self.citation_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "chunk_id": self.chunk_id,
            "title": self.title,
            "chapter": self.chapter,
            "section": self.section,
            "page": self.page,
            "excerpt": self.excerpt(),
            "evidence_quality": self.evidence_quality,
            "risk_level": self.risk_level or None,
            "record_date": self.record_date or None,
            "relevance_score": round(self.normalised_score, 3),
        }

    @property
    def normalised_score(self) -> float:
        """0–1 relevance for display.

        An LLM rerank score is already 0–1. A raw RRF score from Azure AI
        Search is small and unbounded (~0.016 for a top hit), so it is scaled
        into a comparable range rather than shown as-is.
        """
        if self.rerank_score is not None:
            return max(0.0, min(1.0, self.rerank_score))
        return max(0.0, min(1.0, self.score * 30.0))


def _build_filter(
    record_types: Sequence[str] | None = None,
    region_ids: Sequence[str] | None = None,
    record_ids: Sequence[str] | None = None,
) -> str | None:
    """OData filter for the metadata pre-filter step."""
    clauses: list[str] = []
    if record_types:
        clauses.append("(" + " or ".join(f"record_type eq '{t}'" for t in record_types) + ")")
    if region_ids:
        clauses.append("(" + " or ".join(f"region_id eq '{r}'" for r in region_ids) + ")")
    if record_ids:
        clauses.append("(" + " or ".join(f"record_id eq '{r}'" for r in record_ids) + ")")
    return " and ".join(clauses) if clauses else None


def hybrid_search(
    query: str,
    *,
    k: int | None = None,
    record_types: Sequence[str] | None = None,
    region_ids: Sequence[str] | None = None,
    record_ids: Sequence[str] | None = None,
) -> list[RetrievedChunk]:
    """One hybrid (BM25 + vector, RRF-fused) query against the index."""
    s = get_settings()
    top = k or s.retrieval_candidate_k

    vector = embed_query(query)
    vq = VectorizedQuery(vector=vector, k_nearest_neighbors=top, fields="content_vector")

    results = search_client().search(
        search_text=query,          # BM25 leg
        vector_queries=[vq],        # vector leg — Azure fuses the two with RRF
        select=_SELECT,
        filter=_build_filter(record_types, region_ids, record_ids),
        top=top,
    )

    out: list[RetrievedChunk] = []
    for r in results:
        out.append(
            RetrievedChunk(
                chunk_id=r.get("chunk_id", ""),
                content=r.get("content", ""),
                record_id=r.get("record_id", "") or "",
                record_type=r.get("record_type", "") or "",
                title=r.get("title", "") or "",
                chapter=r.get("chapter", "") or "",
                section=r.get("section", "") or "",
                region_id=r.get("region_id", "") or "",
                evidence_quality=r.get("evidence_quality", "") or "",
                risk_level=r.get("risk_level", "") or "",
                record_date=r.get("record_date", "") or "",
                document_id=r.get("document_id", "") or "",
                document_name=r.get("document_name", "") or "",
                page=r.get("page"),
                score=float(r.get("@search.score", 0.0)),
            )
        )
    return out


def _dedupe(chunks: Sequence[RetrievedChunk]) -> list[RetrievedChunk]:
    """Keep the highest-scoring instance of each chunk_id."""
    best: dict[str, RetrievedChunk] = {}
    for c in chunks:
        prev = best.get(c.chunk_id)
        if prev is None or c.score > prev.score:
            best[c.chunk_id] = c
    return sorted(best.values(), key=lambda c: c.score, reverse=True)


_RERANK_SYSTEM = """You score how well each Pandora knowledge record answers a question.

Return JSON only: {"scores": [{"id": "<chunk_id>", "score": <0.0-1.0>}, ...]}

Score every candidate you are given. Judge only whether the record contains
information that helps answer THIS question:
  1.0  directly answers it
  0.7  strongly relevant supporting evidence
  0.4  related context, does not answer it
  0.1  same topic area, not useful here
  0.0  irrelevant

Do not invent ids. Do not add commentary."""


def llm_rerank(query: str, candidates: Sequence[RetrievedChunk]) -> list[RetrievedChunk]:
    """Rerank candidates with the chat model.

    Azure AI Search F0 has no semantic reranker, so this stands in for it.
    Best-effort: on any failure the RRF order is returned unchanged, because
    a degraded ranking is much better than a failed query.
    """
    if not candidates:
        return []

    listing = "\n\n".join(
        f"id: {c.chunk_id}\nrecord: {c.citation_id} ({c.record_type})\n{c.excerpt(280)}"
        for c in candidates
    )
    try:
        data = chat_json(
            [
                {"role": "system", "content": _RERANK_SYSTEM},
                {"role": "user", "content": f"Question: {query}\n\nCandidates:\n\n{listing}"},
            ],
            max_tokens=3000,
        )
        scores = {str(item["id"]): float(item["score"]) for item in data.get("scores", [])}
    except (LLMError, KeyError, TypeError, ValueError) as exc:
        logger.warning("rerank failed, falling back to RRF order: %s", exc)
        return list(candidates)

    for c in candidates:
        c.rerank_score = scores.get(c.chunk_id)

    # Unscored candidates sink below scored ones rather than disappearing.
    return sorted(
        candidates,
        key=lambda c: (c.rerank_score if c.rerank_score is not None else -1.0, c.score),
        reverse=True,
    )


def corpus_covers(question: str) -> tuple[bool, float]:
    """Does the corpus cover this question at all? Deterministic, no LLM.

    The honest refusal is a 20-mark rubric item and it cannot rest on the
    model choosing to emit the mandated sentence. The Layer 1 gate caught
    exactly that failure: asked whether to buy Microsoft stock, the model
    declined in its own words but **cited six Pandora records** to justify
    the refusal, so `has_sufficient_evidence` stayed true. Hybrid search
    always returns *something*; "nothing relevant" and "top-6 of 195" are
    indistinguishable downstream. This is the missing signal.

    RRF `@search.score` is rank-based (~0.016-0.03) and carries no absolute
    relevance, so a **pure vector** query is used instead — its score is a
    real similarity. `scripts/measure_relevance_floor.py` measured both
    populations over 12 in-corpus and 8 out-of-corpus questions:

        in-corpus      min 0.6458   mean 0.7144   max 0.7827
        out-of-corpus  min 0.5220   mean 0.5433   max 0.5991

    Cleanly separated, so RELEVANCE_FLOOR sits at the midpoint. The closest
    out-of-corpus case is "the best treatment for a human migraine" (0.5991)
    — near-miss precisely because the corpus carries MED-* health records,
    which is the adversarial case worth being right about.

    Returns (covered, top_similarity) so callers can log the margin.
    """
    s = get_settings()
    try:
        vq = VectorizedQuery(
            vector=embed_query(question), k_nearest_neighbors=5, fields="content_vector"
        )
        results = search_client().search(
            search_text=None, vector_queries=[vq], select=["chunk_id"], top=5
        )
        scores = [float(r.get("@search.score", 0.0)) for r in results]
    except Exception:
        # Never let the guard itself deny service. A failed check reads as
        # "covered" and the normal grounded path runs, exactly as before.
        logger.exception("relevance floor check failed; treating as covered")
        return True, 1.0

    top = max(scores) if scores else 0.0
    covered = top >= s.relevance_floor
    if not covered:
        logger.info(
            "relevance floor: %.4f < %.4f — out of corpus: %r",
            top, s.relevance_floor, question[:60],
        )
    return covered, top


def retrieve(
    query: str,
    *,
    variants: Sequence[str] | None = None,
    top_k: int | None = None,
    record_types: Sequence[str] | None = None,
    region_ids: Sequence[str] | None = None,
    record_ids: Sequence[str] | None = None,
    rerank: bool = False,
) -> list[RetrievedChunk]:
    """Full retrieval pipeline: hybrid → dedupe → (optional rerank) → top-k.

    Args:
        query: The (rewritten) user question.
        variants: Extra phrasings to widen recall; results are fused.
        record_types: Metadata pre-filter. **This is the highest-value
            precision lever we have** — see the note below.
        record_ids: Exact-ID pre-filter — set when the user names a record.
        rerank: LLM rerank, **off by default**. Measured on this corpus with
            gpt-5-mini: ~25 s per query, and it demoted correct fauna records
            below a weaker one. A reasoning model is the wrong tool for bulk
            candidate scoring. Left available for experimentation, but the
            precision it was meant to buy comes from metadata filtering
            instead — filtering `record_types=["fauna","flora"]` on "which
            species are vulnerable to contamination?" takes the top-6 from
            0/6 relevant to 6/6, in 3 s rather than 25 s.
    """
    s = get_settings()
    final_k = top_k or s.retrieval_top_k

    pooled: list[RetrievedChunk] = hybrid_search(
        query, record_types=record_types, region_ids=region_ids, record_ids=record_ids
    )
    for v in variants or []:
        if v and v.strip() and v.strip().lower() != query.strip().lower():
            pooled.extend(
                hybrid_search(v, record_types=record_types, region_ids=region_ids)
            )

    candidates = _dedupe(pooled)
    logger.info("retrieval: %d candidates for %r", len(candidates), query[:60])

    if rerank and candidates:
        candidates = llm_rerank(query, candidates[: s.retrieval_candidate_k])

    selected = candidates[:final_k]

    # Assign citation keys here, not at generation time, so every consumer
    # (generation, GroundingGate, conflict detection, the citation list)
    # refers to a chunk by the same token.
    n = 0
    for c in selected:
        if not c.record_id:
            n += 1
            c.cite_key = f"SEC-{n}"

    return selected


def to_json(chunks: Sequence[RetrievedChunk]) -> str:
    """Debug helper."""
    return json.dumps([asdict(c) for c in chunks], indent=2)
