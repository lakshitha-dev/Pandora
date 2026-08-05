"""`/api/v1/documents` — upload, list, poll, delete (API_CONTRACT §1.3)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Query, Response, UploadFile, status

from app.core import errors
from app.core.dependencies import AgentDep, DbSession, SettingsDep, UserDep
from app.schemas.common import DocumentStatus, ErrorEnvelope
from app.schemas.documents import DocumentListResponse, DocumentOut
from app.services import documents as document_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List documents",
    responses={401: {"model": ErrorEnvelope}},
)
async def list_documents(
    session: DbSession,
    user: UserDep,
    status_filter: Annotated[DocumentStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    rows, total = await document_service.list_documents(
        session, user.id, status=status_filter, limit=limit, offset=offset
    )
    return DocumentListResponse(
        documents=[DocumentOut.model_validate(document_service.as_utc(row)) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=DocumentOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document (indexing is async)",
    responses={
        400: {"model": ErrorEnvelope, "description": "unsupported_file_type · file_too_large"},
        401: {"model": ErrorEnvelope},
    },
)
async def upload_document(
    session: DbSession,
    agent: AgentDep,
    user: UserDep,
    settings: SettingsDep,
    background: BackgroundTasks,
    file: Annotated[UploadFile, File(description="PDF, DOCX, CSV or TXT — max 10 MB")],
) -> DocumentOut:
    file_name = (file.filename or "").strip()
    if not file_name:
        raise errors.invalid_request("The uploaded file has no name.")

    content_type = document_service.resolve_content_type(file_name, file.content_type, settings)

    content = await file.read()
    if not content:
        raise errors.invalid_request(f"'{file_name}' is empty.")
    if len(content) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes / (1024 * 1024)
        raise errors.file_too_large(
            f"'{file_name}' is {len(content) / (1024 * 1024):.1f} MB. "
            f"The limit is {limit_mb:.0f} MB."
        )

    document = await document_service.create_document(
        session,
        user_id=user.id,
        file_name=file_name,
        content_type=content_type,
        size_bytes=len(content),
    )
    # Committed by the session dependency before the background task runs.
    result = DocumentOut.model_validate(document_service.as_utc(document))

    background.add_task(
        document_service.ingest_document,
        document_id=document.id,
        file_name=file_name,
        content_type=content_type,
        content=content,
        agent=agent,
    )
    return result


@router.get(
    "/{document_id}",
    response_model=DocumentOut,
    summary="Get one document — poll this for indexing progress",
    responses={401: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def get_document(document_id: uuid.UUID, session: DbSession, user: UserDep) -> DocumentOut:
    document = await document_service.get_document(session, user.id, document_id)
    return DocumentOut.model_validate(document_service.as_utc(document))


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document and its vectors",
    responses={
        401: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope, "description": "corpus_document_immutable"},
        404: {"model": ErrorEnvelope},
        409: {"model": ErrorEnvelope, "description": "document_already_indexing"},
    },
)
async def delete_document(
    document_id: uuid.UUID, session: DbSession, agent: AgentDep, user: UserDep
) -> Response:
    await document_service.delete_document(session, agent, user.id, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
