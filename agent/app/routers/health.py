"""GET /health — liveness plus the one field that matters most.

`corpus_indexed: false` means no query can work. The gateway checks it and
returns 422 rather than letting the model answer from pretrained knowledge.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from app.core.llm import llm_reachable
from app.ingestion.search_index import document_count, search_client, search_reachable
from app.models.schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])

VERSION = "0.1.0"


def _record_count() -> int:
    """Count indexed chunks that carry a corpus record ID."""
    try:
        results = search_client().search(
            search_text="*",
            filter="record_id ne ''",
            select=["chunk_id"],
            include_total_count=True,
            top=1,
        )
        return results.get_count() or 0
    except Exception:  # noqa: BLE001
        return 0


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    search_ok = search_reachable()
    llm_ok = llm_reachable()
    chunks = document_count() if search_ok else 0
    records = _record_count() if search_ok and chunks > 0 else 0

    corpus_indexed = chunks > 0
    status = "ok" if (search_ok and llm_ok and corpus_indexed) else "degraded"

    return HealthResponse(
        status=status,
        search_index_reachable=search_ok,
        llm_reachable=llm_ok,
        corpus_indexed=corpus_indexed,
        corpus_chunk_count=max(chunks, 0),
        corpus_record_count=records,
        # LLM rerank measured at ~25s/query on gpt-5-mini and it degraded
        # ranking quality, so it is off. F0 has no semantic ranker.
        rerank_mode="none",
        version=VERSION,
    )
