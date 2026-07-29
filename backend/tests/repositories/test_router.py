from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.exceptions import (
    InvalidGitHubRepositoryURLError,
    RepositoryAlreadyExistsError,
    RepositoryNotFoundError,
)
from src.ingestion.models import IngestionJob, IngestionJobStatus
from src.repositories.dependencies import (
    get_repository_import_service,
    get_repository_service,
)
from src.repositories.import_service import (
    RepositoryImportResult,
    RepositoryImportService,
)
from src.repositories.models import Repository
from src.repositories.service import RepositoryService
from src.repository_versions.models import RepositoryVersion

GITHUB_URL = "https://github.com/kumari-anushka/trace"
COMMIT_SHA = "a" * 40


def make_repository() -> Repository:
    now = datetime.now(UTC)

    repository = Repository(
        github_id=123456789,
        github_url=GITHUB_URL,
        owner="kumari-anushka",
        name="trace",
        default_branch="main",
    )

    repository.id = uuid4()
    repository.created_at = now
    repository.updated_at = now

    return repository


def make_repository_version(
    repository: Repository,
) -> RepositoryVersion:
    repository_version = RepositoryVersion(
        repository_id=repository.id,
        commit_sha=COMMIT_SHA,
        branch="main",
    )

    repository_version.id = uuid4()
    repository_version.created_at = datetime.now(UTC)

    return repository_version


def make_ingestion_job(
    repository_version: RepositoryVersion,
) -> IngestionJob:
    now = datetime.now(UTC)

    ingestion_job = IngestionJob(
        repository_version_id=repository_version.id,
        status=IngestionJobStatus.QUEUED,
        progress=0,
    )

    ingestion_job.id = uuid4()
    ingestion_job.created_at = now
    ingestion_job.updated_at = now
    ingestion_job.started_at = None
    ingestion_job.completed_at = None
    ingestion_job.error_message = None

    return ingestion_job


def override_repository_import_service(
    app: FastAPI,
    service: AsyncMock,
) -> None:
    def dependency_override() -> RepositoryImportService:
        return cast(RepositoryImportService, service)

    app.dependency_overrides[get_repository_import_service] = dependency_override


def override_repository_service(
    app: FastAPI,
    service: AsyncMock,
) -> None:
    def dependency_override() -> RepositoryService:
        return cast(RepositoryService, service)

    app.dependency_overrides[get_repository_service] = dependency_override


def test_import_repository_returns_created_resources(
    app: FastAPI,
    client: TestClient,
) -> None:
    repository = make_repository()
    repository_version = make_repository_version(repository)
    ingestion_job = make_ingestion_job(repository_version)

    service = AsyncMock(spec=RepositoryImportService)
    service.import_repository.return_value = RepositoryImportResult(
        repository=repository,
        repository_version=repository_version,
        ingestion_job=ingestion_job,
    )

    override_repository_import_service(app, service)

    response = client.post(
        "/repositories",
        json={
            "github_url": GITHUB_URL,
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["repository"]["id"] == str(repository.id)
    assert body["repository"]["github_id"] == 123456789
    assert body["repository"]["github_url"] == GITHUB_URL
    assert body["repository"]["owner"] == "kumari-anushka"
    assert body["repository"]["name"] == "trace"
    assert body["repository"]["default_branch"] == "main"

    assert body["repository_version"]["id"] == str(repository_version.id)
    assert body["repository_version"]["repository_id"] == str(repository.id)
    assert body["repository_version"]["commit_sha"] == COMMIT_SHA
    assert body["repository_version"]["branch"] == "main"

    assert body["ingestion_job"]["id"] == str(ingestion_job.id)
    assert body["ingestion_job"]["repository_version_id"] == str(repository_version.id)
    assert body["ingestion_job"]["status"] == "queued"
    assert body["ingestion_job"]["progress"] == 0
    assert body["ingestion_job"]["error_message"] is None

    service.import_repository.assert_awaited_once_with(
        github_url=GITHUB_URL,
    )


def test_import_repository_returns_422_for_invalid_url(
    app: FastAPI,
    client: TestClient,
) -> None:
    service = AsyncMock(spec=RepositoryImportService)
    service.import_repository.side_effect = InvalidGitHubRepositoryURLError()

    override_repository_import_service(app, service)

    response = client.post(
        "/repositories",
        json={
            "github_url": ("https://github.com/kumari-anushka/trace.git"),
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "message": "Invalid GitHub repository URL",
    }

    service.import_repository.assert_awaited_once_with(
        github_url=("https://github.com/kumari-anushka/trace.git"),
    )


def test_import_repository_returns_422_for_malformed_url(
    app: FastAPI,
    client: TestClient,
) -> None:
    service = AsyncMock(spec=RepositoryImportService)

    override_repository_import_service(app, service)

    response = client.post(
        "/repositories",
        json={
            "github_url": "not-a-url",
        },
    )

    assert response.status_code == 422

    body = response.json()

    assert body["message"] == "Invalid request"
    assert isinstance(body["errors"], list)
    assert body["errors"]

    service.import_repository.assert_not_awaited()


def test_import_repository_returns_409_when_repository_exists(
    app: FastAPI,
    client: TestClient,
) -> None:
    service = AsyncMock(spec=RepositoryImportService)
    service.import_repository.side_effect = RepositoryAlreadyExistsError()

    override_repository_import_service(app, service)

    response = client.post(
        "/repositories",
        json={
            "github_url": GITHUB_URL,
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "message": "Repository already exists",
    }


def test_list_repositories_returns_repositories(
    app: FastAPI,
    client: TestClient,
) -> None:
    repositories = [
        make_repository(),
        make_repository(),
    ]

    service = AsyncMock(spec=RepositoryService)
    service.list_repositories.return_value = repositories

    override_repository_service(app, service)

    response = client.get("/repositories")

    assert response.status_code == 200

    body = response.json()

    assert len(body["repositories"]) == 2
    assert body["repositories"][0]["id"] == str(repositories[0].id)
    assert body["repositories"][1]["id"] == str(repositories[1].id)

    service.list_repositories.assert_awaited_once_with()


def test_list_repositories_returns_empty_list(
    app: FastAPI,
    client: TestClient,
) -> None:
    service = AsyncMock(spec=RepositoryService)
    service.list_repositories.return_value = []

    override_repository_service(app, service)

    response = client.get("/repositories")

    assert response.status_code == 200
    assert response.json() == {
        "repositories": [],
    }


def test_get_repository_returns_repository(
    app: FastAPI,
    client: TestClient,
) -> None:
    repository = make_repository()

    service = AsyncMock(spec=RepositoryService)
    service.get_repository.return_value = repository

    override_repository_service(app, service)

    response = client.get(
        f"/repositories/{repository.id}",
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(repository.id)
    assert response.json()["github_url"] == GITHUB_URL

    service.get_repository.assert_awaited_once_with(
        repository.id,
    )


def test_get_repository_returns_404_when_missing(
    app: FastAPI,
    client: TestClient,
) -> None:
    repository_id = uuid4()

    service = AsyncMock(spec=RepositoryService)
    service.get_repository.side_effect = RepositoryNotFoundError()

    override_repository_service(app, service)

    response = client.get(
        f"/repositories/{repository_id}",
    )

    assert response.status_code == 404
    assert response.json() == {
        "message": "Repository not found",
    }


def test_get_repository_returns_422_for_invalid_uuid(
    app: FastAPI,
    client: TestClient,
) -> None:
    service = AsyncMock(spec=RepositoryService)

    override_repository_service(app, service)

    response = client.get(
        "/repositories/not-a-uuid",
    )

    assert response.status_code == 422
    assert response.json()["message"] == "Invalid request"

    service.get_repository.assert_not_awaited()


def test_delete_repository_returns_success_message(
    app: FastAPI,
    client: TestClient,
) -> None:
    repository_id = uuid4()

    service = AsyncMock(spec=RepositoryService)

    override_repository_service(app, service)

    response = client.delete(
        f"/repositories/{repository_id}",
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Repository deleted successfully",
    }

    service.delete_repository.assert_awaited_once_with(
        repository_id,
    )


def test_delete_repository_returns_404_when_missing(
    app: FastAPI,
    client: TestClient,
) -> None:
    repository_id = uuid4()

    service = AsyncMock(spec=RepositoryService)
    service.delete_repository.side_effect = RepositoryNotFoundError()

    override_repository_service(app, service)

    response = client.delete(
        f"/repositories/{repository_id}",
    )

    assert response.status_code == 404
    assert response.json() == {
        "message": "Repository not found",
    }
