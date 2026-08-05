"""Document metadata shapes (API_CONTRACT §1.3)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.common import DocumentStatus, Paged, UtcDatetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_name: str
    content_type: str
    size_bytes: int
    page_count: int | None = None
    chunk_count: int | None = None
    status: DocumentStatus
    error_message: str | None = None
    uploaded_at: UtcDatetime
    indexed_at: UtcDatetime | None = None


class DocumentListResponse(Paged):
    documents: list[DocumentOut]
