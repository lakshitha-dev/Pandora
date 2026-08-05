"""Azure AI Search — index schema, creation, and upsert.

We use the azure-search-documents SDK directly rather than LangChain's
AzureSearch vectorstore wrapper. The wrapper assumes its own field schema;
we need twelve custom filterable fields and precise control over the hybrid
query shape (SOLUTION.md §4.3).

F0 tier constraint: no semantic reranker (that is Basic+). Reranking, if we
add it, is an LLM call over the candidate set — see chains/retrieval.py.
"""

from __future__ import annotations

import logging
from typing import Iterable, Sequence

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    HnswParameters,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchAlgorithmMetric,
    VectorSearchProfile,
)

from app.core.config import get_settings
from app.ingestion.parse import Chunk

logger = logging.getLogger(__name__)

_VECTOR_PROFILE = "pandora-hnsw-profile"
_VECTOR_ALGO = "pandora-hnsw"


def _credential() -> AzureKeyCredential:
    return AzureKeyCredential(get_settings().azure_search_api_key)


def index_client() -> SearchIndexClient:
    s = get_settings()
    return SearchIndexClient(endpoint=s.azure_search_endpoint, credential=_credential())


def search_client() -> SearchClient:
    s = get_settings()
    return SearchClient(
        endpoint=s.azure_search_endpoint,
        index_name=s.azure_search_index_name,
        credential=_credential(),
    )


def build_index_definition() -> SearchIndex:
    """The Pandora knowledge index.

    Every metadata field that retrieval filters on, or that a source card
    displays, is declared here. The brief requires document name, section or
    page, excerpt, and relevance score on every citation — so all of those
    must be retrievable.
    """
    s = get_settings()

    fields = [
        SimpleField(name="chunk_id", type=SearchFieldDataType.String, key=True),
        # BM25 leg of the hybrid query.
        SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
        SearchableField(name="title", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
        # record_id is searchable AND filterable: embeddings handle exact
        # tokens like "INV-4471" or "INC-005" poorly, so BM25 must see it.
        SearchableField(name="record_id", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="record_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="chapter", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SimpleField(name="section", type=SearchFieldDataType.String, retrievable=True),
        SimpleField(name="region_id", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="evidence_quality", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="risk_level", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="record_date", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SimpleField(name="document_id", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="document_name", type=SearchFieldDataType.String, retrievable=True),
        SimpleField(name="page", type=SearchFieldDataType.Int32, filterable=True, retrievable=True),
        # Vector leg.
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=s.embedding_dimensions,
            vector_search_profile_name=_VECTOR_PROFILE,
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name=_VECTOR_ALGO,
                parameters=HnswParameters(
                    m=4,
                    ef_construction=400,
                    ef_search=500,
                    metric=VectorSearchAlgorithmMetric.COSINE,
                ),
            )
        ],
        profiles=[VectorSearchProfile(name=_VECTOR_PROFILE, algorithm_configuration_name=_VECTOR_ALGO)],
    )

    return SearchIndex(name=s.azure_search_index_name, fields=fields, vector_search=vector_search)


def ensure_index(recreate: bool = False) -> str:
    """Create the index if absent. Idempotent.

    Args:
        recreate: drop and rebuild. Needed when the schema changes, since
            Azure AI Search cannot alter most field attributes in place.
    """
    s = get_settings()
    client = index_client()

    if recreate:
        try:
            client.delete_index(s.azure_search_index_name)
            logger.info("deleted existing index %s", s.azure_search_index_name)
        except ResourceNotFoundError:
            pass

    client.create_or_update_index(build_index_definition())
    logger.info("index %s ready", s.azure_search_index_name)
    return s.azure_search_index_name


def index_exists() -> bool:
    try:
        index_client().get_index(get_settings().azure_search_index_name)
        return True
    except ResourceNotFoundError:
        return False


def chunk_to_document(chunk: Chunk, vector: Sequence[float]) -> dict:
    """Map a parsed Chunk plus its embedding into an index document."""
    return {
        "chunk_id": chunk.chunk_id,
        "content": chunk.content,
        "title": chunk.title,
        "record_id": chunk.record_id or "",
        "record_type": chunk.record_type,
        "chapter": chunk.chapter,
        "section": chunk.section,
        "region_id": chunk.region_id or "",
        "evidence_quality": chunk.evidence_quality,
        "risk_level": chunk.risk_level or "",
        "record_date": chunk.record_date or "",
        "document_id": chunk.document_id,
        "document_name": chunk.document_name,
        "page": chunk.page,
        "content_vector": list(vector),
    }


def upload(documents: Iterable[dict], batch_size: int = 100) -> int:
    """Upsert documents into the index. Returns the count succeeded."""
    client = search_client()
    docs = list(documents)
    total = 0

    for start in range(0, len(docs), batch_size):
        batch = docs[start : start + batch_size]
        results = client.upload_documents(documents=batch)
        failed = [r for r in results if not r.succeeded]
        if failed:
            raise RuntimeError(
                f"{len(failed)} document(s) failed to index; first error: "
                f"{failed[0].key} -> {failed[0].error_message}"
            )
        total += len(batch)
        logger.info("indexed %d/%d", total, len(docs))

    return total


def _escape(value: str) -> str:
    """OData string literals escape a single quote by doubling it."""
    return value.replace("'", "''")


def list_by_record_type(
    record_type: str,
    *,
    risk_level: str | None = None,
    region_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    select: Sequence[str] | None = None,
) -> tuple[list[dict], int]:
    """Filtered metadata listing — no vector query, no LLM call.

    API_CONTRACT §1.6 is explicit that the incident register is a projection
    of metadata the index already holds. `record_type`, `risk_level`, and
    `region_id` are all filterable on the index, so this is a pure filter with
    `search_text="*"` rather than a retrieval call, and it needs no reseed.

    Returns `(rows, total)` — `total` is the unpaged count, for the pager.
    """
    clauses = [f"record_type eq '{_escape(record_type)}'"]
    if risk_level:
        clauses.append(f"risk_level eq '{_escape(risk_level)}'")
    if region_id:
        clauses.append(f"region_id eq '{_escape(region_id)}'")

    results = search_client().search(
        search_text="*",
        filter=" and ".join(clauses),
        select=list(select) if select else None,
        include_total_count=True,
        skip=offset,
        top=limit,
    )
    rows = [dict(r) for r in results]
    total = results.get_count() or 0
    return rows, total


def delete_by_document_id(document_id: str) -> int:
    """Remove every chunk belonging to a document. Returns the count deleted.

    Deletion crosses two stores. Orphaned vectors mean the assistant cites
    documents the user already deleted, so the gateway calls this on delete.
    """
    client = search_client()
    deleted = 0
    while True:
        results = client.search(
            search_text="*",
            filter=f"document_id eq '{_escape(document_id)}'",
            select=["chunk_id"],
            top=1000,
        )
        keys = [{"chunk_id": r["chunk_id"]} for r in results]
        if not keys:
            break
        client.delete_documents(documents=keys)
        deleted += len(keys)
        if len(keys) < 1000:
            break
    logger.info("deleted %d chunk(s) for document %s", deleted, document_id)
    return deleted


def document_count() -> int:
    """How many documents are currently in the index."""
    try:
        return search_client().get_document_count()
    except Exception:  # noqa: BLE001
        return -1


def search_reachable() -> bool:
    """Liveness probe used by GET /health."""
    try:
        index_client().get_index(get_settings().azure_search_index_name)
        return True
    except Exception:  # noqa: BLE001
        logger.warning("search health probe failed", exc_info=True)
        return False
