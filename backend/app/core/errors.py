"""The standard error envelope — every non-2xx response, no exceptions.

    {"error": {"code": "document_not_found", "message": "...", "details": null}}

Codes are the ones enumerated in docs/API_CONTRACT.md § Error envelope. Adding a
code means adding it there first.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Raised anywhere in the app; rendered as the standard envelope."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


# --- The catalogue. One constructor per documented code. ---------------------


def invalid_request(message: str, details: Any | None = None) -> AppError:
    return AppError(status.HTTP_400_BAD_REQUEST, "invalid_request", message, details)


def unsupported_file_type(message: str, details: Any | None = None) -> AppError:
    return AppError(status.HTTP_400_BAD_REQUEST, "unsupported_file_type", message, details)


def file_too_large(message: str, details: Any | None = None) -> AppError:
    return AppError(status.HTTP_400_BAD_REQUEST, "file_too_large", message, details)


def unauthenticated(message: str = "Missing or invalid credentials.") -> AppError:
    return AppError(status.HTTP_401_UNAUTHORIZED, "unauthenticated", message)


def forbidden(message: str = "You do not have access to this resource.") -> AppError:
    return AppError(status.HTTP_403_FORBIDDEN, "forbidden", message)


def document_not_found(document_id: Any) -> AppError:
    return AppError(
        status.HTTP_404_NOT_FOUND,
        "document_not_found",
        f"No document exists with id {document_id}",
    )


def report_not_found(answer_id: Any) -> AppError:
    return AppError(
        status.HTTP_404_NOT_FOUND,
        "report_not_found",
        f"No situation report exists with id {answer_id}",
    )


def corpus_document_immutable() -> AppError:
    """The preloaded corpus cannot be deleted. It's the demo."""
    return AppError(
        status.HTTP_403_FORBIDDEN,
        "corpus_document_immutable",
        "The preloaded Pandora corpus cannot be deleted.",
    )


def document_already_indexing(document_id: Any) -> AppError:
    return AppError(
        status.HTTP_409_CONFLICT,
        "document_already_indexing",
        f"Document {document_id} is still indexing and cannot be deleted yet.",
    )


def corpus_not_indexed() -> AppError:
    """The index is empty — say so rather than let the model answer from
    pretrained knowledge, which on a fictional corpus is always a hallucination."""
    return AppError(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "corpus_not_indexed",
        "The Pandora knowledge corpus is not indexed yet. Seed the corpus before asking a question.",
    )


def internal_error(message: str = "Something went wrong on our side.") -> AppError:
    return AppError(status.HTTP_500_INTERNAL_SERVER_ERROR, "internal_error", message)


def agent_service_unavailable(message: str = "The agent service is unreachable.") -> AppError:
    return AppError(status.HTTP_502_BAD_GATEWAY, "agent_service_unavailable", message)


def agent_service_timeout(message: str = "The agent service did not respond in time.") -> AppError:
    return AppError(status.HTTP_504_GATEWAY_TIMEOUT, "agent_service_timeout", message)


# --- Rendering ---------------------------------------------------------------

_STATUS_TO_CODE = {
    400: "invalid_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "invalid_request",
    409: "conflict",
    413: "file_too_large",
    415: "unsupported_file_type",
    422: "invalid_request",
    500: "internal_error",
    502: "agent_service_unavailable",
    504: "agent_service_timeout",
}


def error_response(
    status_code: int, code: str, message: str, details: Any | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("app_error code=%s message=%s", exc.code, exc.message)
        return error_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's default 422 body is not our envelope. Field errors go in `details`.
        details = [
            {"field": ".".join(str(p) for p in err.get("loc", ())), "message": err.get("msg", "")}
            for err in exc.errors()
        ]
        return error_response(
            status.HTTP_400_BAD_REQUEST,
            "invalid_request",
            "The request body or query parameters are invalid.",
            details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_TO_CODE.get(exc.status_code, "internal_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return error_response(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error path=%s error=%s", request.url.path, exc)
        return error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "Something went wrong on our side.",
        )
