from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.github_client import GitHubClient
from src.core.exceptions import RepositoryNotFoundError
from src.models.ingestion_job import IngestionJob
from src.models.repository import Repository
from src.models.repository_snapshot import RepositorySnapshot
from src.schemas.github import (
    GitHubCommitMetadata,
    GitHubRepositoryMetadata,
)
from src.services.ingestion_coordinator import IngestionCoordinator


def create_coordinator() -> IngestionCoordinator:
    session = AsyncMock(spec=AsyncSession)
    http_client = AsyncMock(spec=httpx.AsyncClient)

    github_client = GitHubClient(
        client=http_client,
    )

    return IngestionCoordinator(
        session,
        github_client=github_client,
    )


@pytest.mark.asyncio
async def test_create_ingestion_uses_github_branch_and_commit() -> None:
    coordinator = create_coordinator()

    repository = MagicMock(spec=Repository)
    repository.id = 1
    repository.owner = "kumari-anushka"
    repository.name = "trace"

    snapshot = MagicMock(spec=RepositorySnapshot)
    job = MagicMock(spec=IngestionJob)

    with (
        patch.object(
            coordinator.repository_service,
            "get_repository",
            new=AsyncMock(return_value=repository),
        ) as get_repository_mock,
        patch.object(
            coordinator.github_client,
            "get_repository",
            new=AsyncMock(
                return_value=GitHubRepositoryMetadata(
                    id=123,
                    name="trace",
                    full_name="kumari-anushka/trace",
                    private=False,
                    default_branch="main",
                ),
            ),
        ) as get_github_repository_mock,
        patch.object(
            coordinator.github_client,
            "get_commit",
            new=AsyncMock(
                return_value=GitHubCommitMetadata(
                    sha="abc123",
                ),
            ),
        ) as get_commit_mock,
        patch.object(
            coordinator.ingestion_service,
            "create_ingestion",
            new=AsyncMock(
                return_value=(snapshot, job),
            ),
        ) as create_ingestion_mock,
    ):
        result = await coordinator.create_ingestion(
            repository_id=1,
        )

    assert result == (snapshot, job)

    get_repository_mock.assert_awaited_once_with(
        repository_id=1,
    )

    get_github_repository_mock.assert_awaited_once_with(
        owner="kumari-anushka",
        name="trace",
    )

    get_commit_mock.assert_awaited_once_with(
        owner="kumari-anushka",
        name="trace",
        ref="main",
    )

    create_ingestion_mock.assert_awaited_once_with(
        repository=repository,
        commit_sha="abc123",
        default_branch="main",
    )


@pytest.mark.asyncio
async def test_create_ingestion_does_not_create_job_when_github_fails() -> None:
    coordinator = create_coordinator()

    repository = MagicMock(spec=Repository)
    repository.id = 1
    repository.owner = "missing"
    repository.name = "repo"

    request = httpx.Request(
        "GET",
        "https://api.github.com/repos/missing/repo",
    )
    response = httpx.Response(
        status_code=404,
        request=request,
    )

    with (
        patch.object(
            coordinator.repository_service,
            "get_repository",
            new=AsyncMock(return_value=repository),
        ),
        patch.object(
            coordinator.github_client,
            "get_repository",
            new=AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Repository not found",
                    request=request,
                    response=response,
                ),
            ),
        ),
        patch.object(
            coordinator.ingestion_service,
            "create_ingestion",
            new=AsyncMock(),
        ) as create_ingestion_mock,
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await coordinator.create_ingestion(
                repository_id=1,
            )

    create_ingestion_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_ingestion_raises_when_repository_not_found() -> None:
    coordinator = create_coordinator()

    with (
        patch.object(
            coordinator.repository_service,
            "get_repository",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            coordinator.github_client,
            "get_repository",
            new=AsyncMock(),
        ) as github_mock,
    ):
        with pytest.raises(RepositoryNotFoundError):
            await coordinator.create_ingestion(
                repository_id=1,
            )

    github_mock.assert_not_awaited()
