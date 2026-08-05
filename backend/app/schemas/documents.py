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
    # How many corpus-style records the chunker detected. 0 means it fell back
    # to narrative chunking, which is normal for an arbitrary uploaded file.
    record_count: int | None = None
    status: DocumentStatus
    # The preloaded Pandora corpus. It is the demo, so it cannot be deleted.
    is_preloaded: bool = False
    error_message: str | None = None
    uploaded_at: UtcDatetime
    indexed_at: UtcDatetime | None = None


class DocumentListResponse(Paged):
    documents: list[DocumentOut]
