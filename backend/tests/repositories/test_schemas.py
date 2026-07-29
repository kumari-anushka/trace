from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.ingestion.models import IngestionJob, IngestionJobStatus
from src.repositories.models import Repository
from src.repositories.schemas import (
    MessageResponse,
    RepositoryImportRequest,
    RepositoryImportResponse,
    RepositoryListResponse,
    RepositoryResponse,
)
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


def test_repository_import_request_accepts_https_url() -> None:
    request = RepositoryImportRequest.model_validate(
        {
            "github_url": GITHUB_URL,
        },
    )

    assert str(request.github_url).rstrip("/") == GITHUB_URL


@pytest.mark.parametrize(
    "github_url",
    [
        "",
        "not-a-url",
        "github.com/kumari-anushka/trace",
    ],
)
def test_repository_import_request_rejects_invalid_url(
    github_url: str,
) -> None:
    with pytest.raises(ValidationError):
        RepositoryImportRequest.model_validate(
            {
                "github_url": github_url,
            },
        )


def test_repository_response_builds_from_model() -> None:
    repository = make_repository()

    response = RepositoryResponse.model_validate(repository)

    assert response.id == repository.id
    assert response.github_id == 123456789
    assert response.github_url == GITHUB_URL
    assert response.owner == "kumari-anushka"
    assert response.name == "trace"
    assert response.default_branch == "main"
    assert response.created_at == repository.created_at
    assert response.updated_at == repository.updated_at


def test_repository_list_response_contains_repositories() -> None:
    repositories = [
        make_repository(),
        make_repository(),
    ]

    response = RepositoryListResponse(
        repositories=[RepositoryResponse.model_validate(repository) for repository in repositories],
    )

    assert len(response.repositories) == 2
    assert response.repositories[0].id == repositories[0].id
    assert response.repositories[1].id == repositories[1].id


def test_repository_list_response_accepts_empty_list() -> None:
    response = RepositoryListResponse(
        repositories=[],
    )

    assert response.repositories == []


def test_repository_import_response_contains_created_resources() -> None:
    repository = make_repository()
    repository_version = make_repository_version(repository)
    ingestion_job = make_ingestion_job(repository_version)

    response = RepositoryImportResponse.model_validate(
        {
            "repository": repository,
            "repository_version": repository_version,
            "ingestion_job": ingestion_job,
        },
    )

    assert response.repository.id == repository.id
    assert response.repository_version.id == repository_version.id
    assert response.ingestion_job.id == ingestion_job.id

    assert response.repository_version.repository_id == repository.id
    assert response.ingestion_job.repository_version_id == (repository_version.id)

    assert response.ingestion_job.status is (IngestionJobStatus.QUEUED)
    assert response.ingestion_job.progress == 0


def test_message_response_contains_message() -> None:
    response = MessageResponse(
        message="Repository deleted successfully",
    )

    assert response.message == "Repository deleted successfully"
