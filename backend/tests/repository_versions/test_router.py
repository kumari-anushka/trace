from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.exceptions import RepositoryVersionNotFoundError
from src.repository_versions.dependencies import (
    get_repository_version_service,
)
from src.repository_versions.models import RepositoryVersion
from src.repository_versions.service import RepositoryVersionService

COMMIT_SHA = "a" * 40


def make_repository_version() -> RepositoryVersion:
    repository_version = RepositoryVersion(
        repository_id=uuid4(),
        commit_sha=COMMIT_SHA,
        branch="main",
    )

    repository_version.id = uuid4()
    repository_version.created_at = datetime.now(UTC)

    return repository_version


def override_repository_version_service(
    app: FastAPI,
    service: AsyncMock,
) -> None:
    def dependency_override() -> RepositoryVersionService:
        return cast(RepositoryVersionService, service)

    app.dependency_overrides[get_repository_version_service] = dependency_override


def test_list_repository_versions_returns_versions(
    app: FastAPI,
    client: TestClient,
) -> None:
    repository_id = uuid4()

    repository_versions = [
        make_repository_version(),
        make_repository_version(),
    ]

    for repository_version in repository_versions:
        repository_version.repository_id = repository_id

    service = AsyncMock(spec=RepositoryVersionService)
    service.list_repository_versions.return_value = repository_versions

    override_repository_version_service(app, service)

    response = client.get(
        "/repository-versions",
        params={
            "repository_id": str(repository_id),
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 2

    assert body[0]["id"] == str(
        repository_versions[0].id,
    )
    assert body[0]["repository_id"] == str(repository_id)
    assert body[0]["commit_sha"] == COMMIT_SHA
    assert body[0]["branch"] == "main"

    assert body[1]["id"] == str(
        repository_versions[1].id,
    )

    service.list_repository_versions.assert_awaited_once_with(
        repository_id,
    )


def test_list_repository_versions_returns_empty_list(
    app: FastAPI,
    client: TestClient,
) -> None:
    repository_id = uuid4()

    service = AsyncMock(spec=RepositoryVersionService)
    service.list_repository_versions.return_value = []

    override_repository_version_service(app, service)

    response = client.get(
        "/repository-versions",
        params={
            "repository_id": str(repository_id),
        },
    )

    assert response.status_code == 200
    assert response.json() == []

    service.list_repository_versions.assert_awaited_once_with(
        repository_id,
    )


def test_list_repository_versions_returns_422_without_repository_id(
    app: FastAPI,
    client: TestClient,
) -> None:
    service = AsyncMock(spec=RepositoryVersionService)

    override_repository_version_service(app, service)

    response = client.get(
        "/repository-versions",
    )

    assert response.status_code == 422
    assert response.json()["message"] == "Invalid request"

    service.list_repository_versions.assert_not_awaited()


def test_list_repository_versions_returns_422_for_invalid_repository_id(
    app: FastAPI,
    client: TestClient,
) -> None:
    service = AsyncMock(spec=RepositoryVersionService)

    override_repository_version_service(app, service)

    response = client.get(
        "/repository-versions",
        params={
            "repository_id": "not-a-uuid",
        },
    )

    assert response.status_code == 422
    assert response.json()["message"] == "Invalid request"

    service.list_repository_versions.assert_not_awaited()


def test_get_repository_version_returns_version(
    app: FastAPI,
    client: TestClient,
) -> None:
    repository_version = make_repository_version()

    service = AsyncMock(spec=RepositoryVersionService)
    service.get_repository_version.return_value = repository_version

    override_repository_version_service(app, service)

    response = client.get(
        f"/repository-versions/{repository_version.id}",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == str(repository_version.id)
    assert body["repository_id"] == str(
        repository_version.repository_id,
    )
    assert body["commit_sha"] == COMMIT_SHA
    assert body["branch"] == "main"

    service.get_repository_version.assert_awaited_once_with(
        repository_version.id,
    )


def test_get_repository_version_returns_404_when_missing(
    app: FastAPI,
    client: TestClient,
) -> None:
    repository_version_id = uuid4()

    service = AsyncMock(spec=RepositoryVersionService)
    service.get_repository_version.side_effect = RepositoryVersionNotFoundError()

    override_repository_version_service(app, service)

    response = client.get(
        f"/repository-versions/{repository_version_id}",
    )

    assert response.status_code == 404
    assert response.json() == {
        "message": "Repository version not found",
    }

    service.get_repository_version.assert_awaited_once_with(
        repository_version_id,
    )


def test_get_repository_version_returns_422_for_invalid_uuid(
    app: FastAPI,
    client: TestClient,
) -> None:
    service = AsyncMock(spec=RepositoryVersionService)

    override_repository_version_service(app, service)

    response = client.get(
        "/repository-versions/not-a-uuid",
    )

    assert response.status_code == 422
    assert response.json()["message"] == "Invalid request"

    service.get_repository_version.assert_not_awaited()
