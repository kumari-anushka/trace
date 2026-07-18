from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    IngestionJobNotFoundError,
    InvalidGitHubRepositoryURLError,
    RepositoryAlreadyExistsError,
    RepositoryNotFoundError,
    SnapshotAlreadyExistsError,
)
from src.db.session import get_db_session
from src.main import app
from src.models.enums import IngestionJobStatus, SnapshotStatus
from src.models.ingestion_job import IngestionJob
from src.models.repository import Repository
from src.models.repository_snapshot import RepositorySnapshot


async def override_get_db_session() -> AsyncGenerator[AsyncSession]:
    yield MagicMock(spec=AsyncSession)


@pytest.fixture
def client() -> Generator[TestClient]:
    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def make_repository(
    *,
    repository_id: int = 1,
    github_url: str = "https://github.com/kumari-anushka/trace",
    owner: str = "kumari-anushka",
    name: str = "trace",
) -> Repository:
    return Repository(
        id=repository_id,
        github_url=github_url,
        owner=owner,
        name=name,
        created_at=datetime.now(UTC),
    )


def make_snapshot() -> RepositorySnapshot:
    return RepositorySnapshot(
        id=1,
        repository_id=1,
        commit_sha="a1b2c3d4e5f6",
        default_branch="main",
        status=SnapshotStatus.PENDING,
        created_at=datetime.now(UTC),
    )


def make_ingestion_job() -> IngestionJob:
    return IngestionJob(
        id=1,
        repository_id=1,
        snapshot_id=1,
        status=IngestionJobStatus.PENDING,
        progress=0,
        error_message=None,
        started_at=None,
        completed_at=None,
        created_at=datetime.now(UTC),
    )


def test_create_repository_returns_created_repository(
    client: TestClient,
) -> None:
    repository = make_repository()
    create_mock = AsyncMock(return_value=repository)

    with patch(
        "src.api.routes.repositories.RepositoryService.create_repository",
        create_mock,
    ):
        response = client.post(
            "/repositories",
            json={
                "github_url": "https://github.com/kumari-anushka/trace",
            },
        )

    assert response.status_code == 201

    body = response.json()

    assert body["id"] == 1
    assert body["github_url"] == "https://github.com/kumari-anushka/trace"
    assert body["owner"] == "kumari-anushka"
    assert body["name"] == "trace"
    assert "created_at" in body

    create_mock.assert_awaited_once_with(
        github_url="https://github.com/kumari-anushka/trace",
    )


def test_create_repository_returns_422_for_invalid_url(
    client: TestClient,
) -> None:
    create_mock = AsyncMock(
        side_effect=InvalidGitHubRepositoryURLError,
    )

    with patch(
        "src.api.routes.repositories.RepositoryService.create_repository",
        create_mock,
    ):
        response = client.post(
            "/repositories",
            json={
                "github_url": "https://example.com/not-github",
            },
        )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Invalid GitHub repository URL",
    }

    create_mock.assert_awaited_once_with(
        github_url="https://example.com/not-github",
    )


def test_create_repository_returns_409_when_repository_exists(
    client: TestClient,
) -> None:
    create_mock = AsyncMock(
        side_effect=RepositoryAlreadyExistsError,
    )

    with patch(
        "src.api.routes.repositories.RepositoryService.create_repository",
        create_mock,
    ):
        response = client.post(
            "/repositories",
            json={
                "github_url": "https://github.com/kumari-anushka/trace",
            },
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Repository already exists",
    }

    create_mock.assert_awaited_once_with(
        github_url="https://github.com/kumari-anushka/trace",
    )


def test_create_repository_returns_422_for_missing_github_url(
    client: TestClient,
) -> None:
    create_mock = AsyncMock()

    with patch(
        "src.api.routes.repositories.RepositoryService.create_repository",
        create_mock,
    ):
        response = client.post(
            "/repositories",
            json={},
        )

    assert response.status_code == 422
    create_mock.assert_not_awaited()


def test_list_repositories_returns_repositories(
    client: TestClient,
) -> None:
    repositories = [
        make_repository(),
        make_repository(
            repository_id=2,
            github_url="https://github.com/fastapi/fastapi",
            owner="fastapi",
            name="fastapi",
        ),
    ]
    list_mock = AsyncMock(return_value=repositories)

    with patch(
        "src.api.routes.repositories.RepositoryService.list_repositories",
        list_mock,
    ):
        response = client.get("/repositories")

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 2
    assert body[0]["id"] == 1
    assert body[0]["owner"] == "kumari-anushka"
    assert body[0]["name"] == "trace"
    assert body[1]["id"] == 2
    assert body[1]["owner"] == "fastapi"
    assert body[1]["name"] == "fastapi"

    list_mock.assert_awaited_once_with()


def test_list_repositories_returns_empty_list(
    client: TestClient,
) -> None:
    list_mock = AsyncMock(return_value=[])

    with patch(
        "src.api.routes.repositories.RepositoryService.list_repositories",
        list_mock,
    ):
        response = client.get("/repositories")

    assert response.status_code == 200
    assert response.json() == []

    list_mock.assert_awaited_once_with()


def test_delete_repository_returns_success_message(
    client: TestClient,
) -> None:
    delete_mock = AsyncMock(return_value=None)

    with patch(
        "src.api.routes.repositories.RepositoryService.delete_repository",
        delete_mock,
    ):
        response = client.delete("/repositories/1")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Repository deleted successfully",
    }

    delete_mock.assert_awaited_once_with(
        repository_id=1,
    )


def test_delete_repository_returns_404_when_not_found(
    client: TestClient,
) -> None:
    delete_mock = AsyncMock(
        side_effect=RepositoryNotFoundError,
    )

    with patch(
        "src.api.routes.repositories.RepositoryService.delete_repository",
        delete_mock,
    ):
        response = client.delete("/repositories/999")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Repository not found",
    }

    delete_mock.assert_awaited_once_with(
        repository_id=999,
    )


def test_delete_repository_returns_422_for_invalid_id(
    client: TestClient,
) -> None:
    delete_mock = AsyncMock()

    with patch(
        "src.api.routes.repositories.RepositoryService.delete_repository",
        delete_mock,
    ):
        response = client.delete(
            "/repositories/not-an-integer",
        )

    assert response.status_code == 422
    delete_mock.assert_not_awaited()


def test_create_ingestion_returns_created_ingestion(
    client: TestClient,
) -> None:
    snapshot = make_snapshot()
    job = make_ingestion_job()
    create_mock = AsyncMock(return_value=(snapshot, job))

    with patch(
        "src.api.routes.repositories.IngestionCoordinator.create_ingestion",
        create_mock,
    ):
        response = client.post(
            "/repositories/1/ingestions",
        )

    assert response.status_code == 201

    body = response.json()

    assert body["snapshot"]["id"] == 1
    assert body["snapshot"]["repository_id"] == 1
    assert body["snapshot"]["commit_sha"] == "a1b2c3d4e5f6"
    assert body["snapshot"]["default_branch"] == "main"
    assert body["snapshot"]["status"] == "pending"

    assert body["job"]["id"] == 1
    assert body["job"]["repository_id"] == 1
    assert body["job"]["snapshot_id"] == 1
    assert body["job"]["status"] == "pending"
    assert body["job"]["progress"] == 0

    create_mock.assert_awaited_once_with(
        repository_id=1,
    )


def test_create_ingestion_returns_404_when_repository_missing(
    client: TestClient,
) -> None:
    create_mock = AsyncMock(
        side_effect=RepositoryNotFoundError,
    )

    with patch(
        "src.api.routes.repositories.IngestionCoordinator.create_ingestion",
        create_mock,
    ):
        response = client.post(
            "/repositories/999/ingestions",
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Repository not found",
    }


def test_create_ingestion_returns_409_when_snapshot_exists(
    client: TestClient,
) -> None:
    create_mock = AsyncMock(
        side_effect=SnapshotAlreadyExistsError,
    )

    with patch(
        "src.api.routes.repositories.IngestionCoordinator.create_ingestion",
        create_mock,
    ):
        response = client.post(
            "/repositories/1/ingestions",
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Snapshot already exists",
    }


def test_create_ingestion_returns_404_when_github_repo_missing(
    client: TestClient,
) -> None:
    request = httpx.Request(
        "GET",
        "https://api.github.com/repos/missing/repo",
    )
    github_response = httpx.Response(
        status_code=404,
        request=request,
    )

    create_mock = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Not Found",
            request=request,
            response=github_response,
        ),
    )

    with patch(
        "src.api.routes.repositories.IngestionCoordinator.create_ingestion",
        create_mock,
    ):
        response = client.post(
            "/repositories/1/ingestions",
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "GitHub repository not found",
    }


def test_create_ingestion_returns_502_for_github_failure(
    client: TestClient,
) -> None:
    request = httpx.Request(
        "GET",
        "https://api.github.com/repos/owner/repo",
    )
    github_response = httpx.Response(
        status_code=500,
        request=request,
    )

    create_mock = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "GitHub failed",
            request=request,
            response=github_response,
        ),
    )

    with patch(
        "src.api.routes.repositories.IngestionCoordinator.create_ingestion",
        create_mock,
    ):
        response = client.post(
            "/repositories/1/ingestions",
        )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "GitHub API request failed",
    }


def test_create_ingestion_returns_422_for_invalid_repository_id(
    client: TestClient,
) -> None:
    create_mock = AsyncMock()

    with patch(
        "src.api.routes.repositories.IngestionCoordinator.create_ingestion",
        create_mock,
    ):
        response = client.post(
            "/repositories/not-an-integer/ingestions",
        )

    assert response.status_code == 422
    create_mock.assert_not_awaited()


def test_get_ingestion_job_returns_job(
    client: TestClient,
) -> None:
    job = make_ingestion_job()
    get_mock = AsyncMock(return_value=job)

    with patch(
        "src.api.routes.repositories.IngestionService.get_ingestion_job",
        get_mock,
    ):
        response = client.get(
            "/repositories/1/ingestions/1",
        )

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == 1
    assert body["repository_id"] == 1
    assert body["snapshot_id"] == 1
    assert body["status"] == "pending"
    assert body["progress"] == 0

    get_mock.assert_awaited_once_with(
        repository_id=1,
        job_id=1,
    )


def test_get_ingestion_job_returns_404_when_missing(
    client: TestClient,
) -> None:
    get_mock = AsyncMock(
        side_effect=IngestionJobNotFoundError,
    )

    with patch(
        "src.api.routes.repositories.IngestionService.get_ingestion_job",
        get_mock,
    ):
        response = client.get(
            "/repositories/1/ingestions/999",
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Ingestion job not found",
    }


def test_get_ingestion_job_returns_422_for_invalid_id(
    client: TestClient,
) -> None:
    get_mock = AsyncMock()

    with patch(
        "src.api.routes.repositories.IngestionService.get_ingestion_job",
        get_mock,
    ):
        response = client.get(
            "/repositories/1/ingestions/not-an-integer",
        )

    assert response.status_code == 422
    get_mock.assert_not_awaited()
