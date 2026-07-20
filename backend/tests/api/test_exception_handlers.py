from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException

from src.api.exception_handlers import register_exception_handlers
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
    RepositoryVersionNotFoundError,
)

ExceptionFactory = Callable[[], Exception]


def create_test_client(
    error: Exception,
) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/error")
    async def raise_error() -> None:
        raise error

    return TestClient(
        app,
        raise_server_exceptions=False,
    )


@pytest.mark.parametrize(
    ("exception_factory", "expected_status", "expected_message"),
    [
        (
            InvalidGitHubRepositoryURLError,
            422,
            "Invalid GitHub repository URL",
        ),
        (
            GitHubRepositoryNotFoundError,
            404,
            "GitHub repository not found",
        ),
        (
            GitHubAPIError,
            502,
            "GitHub API request failed",
        ),
        (
            RepositoryAlreadyExistsError,
            409,
            "Repository already exists",
        ),
        (
            RepositoryNotFoundError,
            404,
            "Repository not found",
        ),
        (
            RepositoryVersionNotFoundError,
            404,
            "Repository version not found",
        ),
        (
            IngestionJobNotFoundError,
            404,
            "Ingestion job not found",
        ),
        (
            InvalidIngestionJobTransitionError,
            409,
            "Invalid ingestion job status transition",
        ),
        (
            InvalidIngestionProgressError,
            422,
            "Ingestion progress must be between 0 and 100",
        ),
        (
            IngestionDispatchError,
            503,
            "Failed to dispatch ingestion job",
        ),
    ],
)
def test_trace_exception_handlers(
    exception_factory: ExceptionFactory,
    expected_status: int,
    expected_message: str,
) -> None:
    client = create_test_client(
        exception_factory(),
    )

    response = client.get("/error")

    assert response.status_code == expected_status
    assert response.json() == {
        "message": expected_message,
    }


def test_trace_exception_handler_preserves_custom_message() -> None:
    client = create_test_client(
        GitHubAPIError(
            "GitHub rate limit exceeded",
        ),
    )

    response = client.get("/error")

    assert response.status_code == 502
    assert response.json() == {
        "message": "GitHub rate limit exceeded",
    }


def test_http_exception_uses_message_key() -> None:
    client = create_test_client(
        HTTPException(
            status_code=418,
            detail="Cannot brew coffee",
        ),
    )

    response = client.get("/error")

    assert response.status_code == 418
    assert response.json() == {
        "message": "Cannot brew coffee",
    }


def test_request_validation_error_uses_message_key() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/numbers/{number}")
    async def get_number(
        number: int,
    ) -> dict[str, int]:
        return {
            "number": number,
        }

    with TestClient(app) as client:
        response = client.get("/numbers/not-a-number")

    assert response.status_code == 422

    body = response.json()

    assert body["message"] == "Invalid request"
    assert isinstance(body["errors"], list)
    assert body["errors"]


def test_unexpected_exception_returns_internal_server_error() -> None:
    client = create_test_client(
        RuntimeError("Sensitive internal failure"),
    )

    response = client.get("/error")

    assert response.status_code == 500
    assert response.json() == {
        "message": "Internal server error",
    }
