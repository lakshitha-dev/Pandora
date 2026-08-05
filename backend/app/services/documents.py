"""Document metadata and the ingestion hand-off.

Upload returns 202 in under a second; indexing happens in the background so the
browser never waits on embedding.
"""

import uuid
from datetime import timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import errors
from app.core.config import Settings
from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import Document
from app.db.session import session_scope
from app.services.agent_client import AgentClient

logger = get_logger(__name__)

# Extension fallbacks: browsers send application/octet-stream for .csv and .docx
# often enough that rejecting on content_type alone loses real uploads.
EXTENSION_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".csv": "text/csv",
    ".txt": "text/plain",
}


def resolve_content_type(file_name: str, declared: str | None, settings: Settings) -> str:
    """Return the content type to store, or raise 400 unsupported_file_type."""
    allowed = settings.allowed_content_type_set
    normalized = (declared or "").split(";")[0].strip().lower()
    if normalized in allowed:
        return normalized

    suffix = ("." + file_name.rsplit(".", 1)[-1].lower()) if "." in file_name else ""
    by_extension = EXTENSION_CONTENT_TYPES.get(suffix)
    if by_extension in allowed:
        return by_extension

    raise errors.unsupported_file_type(
        f"'{file_name}' is not a supported file type. Upload a PDF, DOCX, CSV, or TXT file.",
        details={"received_content_type": declared, "supported": sorted(allowed)},
    )


async def count_indexed_documents(
    session: AsyncSession, user_id: uuid.UUID, document_ids: list[uuid.UUID] | None = None
) -> int:
    stmt = select(func.count(Document.id)).where(
        Document.user_id == user_id, Document.status == "indexed"
    )
    if document_ids:
        stmt = stmt.where(Document.id.in_(document_ids))
    return int((await session.execute(stmt)).scalar_one())


async def get_document(
    session: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID
) -> Document:
    stmt = select(Document).where(Document.id == document_id, Document.user_id == user_id)
    document = (await session.execute(stmt)).scalar_one_or_none()
    if document is None:
        # A document owned by someone else is indistinguishable from one that
        # doesn't exist — never confirm the existence of another user's data.
        raise errors.document_not_found(document_id)
    return document


async def list_documents(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Document], int]:
    filters = [Document.user_id == user_id]
    if status:
        filters.append(Document.status == status)

    total = int(
        (await session.execute(select(func.count(Document.id)).where(*filters))).scalar_one()
    )
    rows = (
        (
            await session.execute(
                select(Document)
                .where(*filters)
                .order_by(Document.uploaded_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), total


async def create_document(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    file_name: str,
    content_type: str,
    size_bytes: int,
) -> Document:
    document = Document(
        id=uuid.uuid4(),
        user_id=user_id,
        file_name=file_name,
        content_type=content_type,
        size_bytes=size_bytes,
        status="pending",
        uploaded_at=utcnow(),
    )
    session.add(document)
    await session.flush()
    return document


async def delete_document(
    session: AsyncSession, agent: AgentClient, user_id: uuid.UUID, document_id: uuid.UUID
) -> None:
    """Delete crosses two stores: the Postgres row and the Azure AI Search vectors."""
    document = await get_document(session, user_id, document_id)
    if document.status == "indexing":
        raise errors.document_already_indexing(document_id)

    if document.status == "indexed":
        removed = await agent.delete_document_vectors(document_id)
        if not removed:
            logger.warning(
                "vectors for document %s were not confirmed deleted; "
                "the Postgres row is being removed anyway",
                document_id,
            )

    await session.delete(document)


async def ingest_document(
    *,
    document_id: uuid.UUID,
    file_name: str,
    content_type: str,
    content: bytes,
    agent: AgentClient,
) -> None:
    """Background task: pending → indexing → indexed | failed.

    Owns its own session — the request's is long gone by the time this runs. Never
    raises: a failed ingestion is a `failed` row with an `error_message`, not a
    crashed worker, and other documents are unaffected.
    """
    try:
        async for session in session_scope():
            await _set_status(session, document_id, "indexing")

        result = await agent.ingest(
            document_id=document_id,
            file_name=file_name,
            content_type=content_type,
            content=content,
        )

        async for session in session_scope():
            document = await session.get(Document, document_id)
            if document is None:  # deleted mid-ingest
                logger.info("document %s vanished during ingestion", document_id)
                return
            if result.status == "indexed":
                document.status = "indexed"
                document.chunk_count = result.chunk_count
                document.page_count = result.page_count
                document.indexed_at = utcnow()
                document.error_message = None
            else:
                document.status = "failed"
                document.error_message = result.error_message or "Indexing failed."
        logger.info("ingest %s -> %s", document_id, result.status)

    except Exception as exc:  # noqa: BLE001 — a background task must not die silently
        logger.exception("ingest failed for %s", document_id)
        message = getattr(exc, "message", None) or str(exc) or "Indexing failed."
        try:
            async for session in session_scope():
                document = await session.get(Document, document_id)
                if document is not None:
                    document.status = "failed"
                    document.error_message = message[:1000]
        except Exception:  # noqa: BLE001
            logger.exception("could not mark %s as failed", document_id)


async def _set_status(session: AsyncSession, document_id: uuid.UUID, status: str) -> None:
    document = await session.get(Document, document_id)
    if document is not None:
        document.status = status


def as_utc(document: Document) -> Document:
    """Postgres returns tz-aware datetimes; SQLite (tests) returns naive ones."""
    if document.uploaded_at is not None and document.uploaded_at.tzinfo is None:
        document.uploaded_at = document.uploaded_at.replace(tzinfo=timezone.utc)
    if document.indexed_at is not None and document.indexed_at.tzinfo is None:
        document.indexed_at = document.indexed_at.replace(tzinfo=timezone.utc)
    return document
