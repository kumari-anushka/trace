import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import (
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_CONTENT,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_502_BAD_GATEWAY,
    HTTP_503_SERVICE_UNAVAILABLE,
)

from src.core.exceptions import (
    GitHubAPIError,
    GitHubRepositoryNotFoundError,
    IngestionDispatchError,
    IngestionJobNotFoundError,
    InvalidGitHubRepositoryURLError,
    InvalidIngestionJobTransitionError,
    InvalidIngestionProgressError,
    RepositoryAlreadyExistsError,
    RepositoryNotFoundError,
    RepositoryVersionAlreadyExistsError,
    RepositoryVersionNotFoundError,
    TraceError,
)

logger = logging.getLogger(__name__)


ERROR_STATUS_CODES: dict[type[TraceError], int] = {
    InvalidGitHubRepositoryURLError: HTTP_422_UNPROCESSABLE_CONTENT,
    GitHubRepositoryNotFoundError: HTTP_404_NOT_FOUND,
    GitHubAPIError: HTTP_502_BAD_GATEWAY,
    RepositoryAlreadyExistsError: HTTP_409_CONFLICT,
    RepositoryNotFoundError: HTTP_404_NOT_FOUND,
    RepositoryVersionAlreadyExistsError: HTTP_409_CONFLICT,
    RepositoryVersionNotFoundError: HTTP_404_NOT_FOUND,
    IngestionJobNotFoundError: HTTP_404_NOT_FOUND,
    InvalidIngestionJobTransitionError: HTTP_409_CONFLICT,
    InvalidIngestionProgressError: HTTP_422_UNPROCESSABLE_CONTENT,
    IngestionDispatchError: HTTP_503_SERVICE_UNAVAILABLE,
}


async def trace_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    del request

    if not isinstance(error, TraceError):
        raise error

    status_code = ERROR_STATUS_CODES.get(
        type(error),
        HTTP_500_INTERNAL_SERVER_ERROR,
    )

    return JSONResponse(
        status_code=status_code,
        content={
            "message": error.message,
        },
    )


async def validation_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    del request

    if not isinstance(error, RequestValidationError):
        raise error

    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "message": "Invalid request",
            "errors": jsonable_encoder(error.errors()),
        },
    )


async def http_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    del request

    if not isinstance(error, StarletteHTTPException):
        raise error

    content: dict[str, Any] = {
        "message": (error.detail if isinstance(error.detail, str) else "Request failed"),
    }

    if not isinstance(error.detail, str):
        content["errors"] = jsonable_encoder(error.detail)

    return JSONResponse(
        status_code=error.status_code,
        content=content,
        headers=error.headers,
    )


async def unexpected_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    logger.exception(
        "Unhandled application error",
        extra={
            "method": request.method,
            "path": request.url.path,
        },
        exc_info=error,
    )

    return JSONResponse(
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "message": "Internal server error",
        },
    )


def register_exception_handlers(
    app: FastAPI,
) -> None:
    app.add_exception_handler(
        TraceError,
        trace_error_handler,
    )
    app.add_exception_handler(
        RequestValidationError,
        validation_error_handler,
    )
    app.add_exception_handler(
        StarletteHTTPException,
        http_error_handler,
    )
    app.add_exception_handler(
        Exception,
        unexpected_error_handler,
    )
