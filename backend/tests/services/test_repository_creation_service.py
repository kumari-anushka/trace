from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.github_client import GitHubClient
from src.core.exceptions import InvalidGitHubRepositoryURLError
from src.models.repository import Repository
from src.services.repository_creation_service import (
    RepositoryCreationService,
)


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def github_client() -> MagicMock:
    return MagicMock(spec=GitHubClient)


@pytest.fixture
def service(
    session: AsyncMock,
    github_client: MagicMock,
) -> RepositoryCreationService:
    return RepositoryCreationService(
        session,
        github_client=github_client,
    )


def make_repository() -> Repository:
    return Repository(
        id=1,
        github_url="https://github.com/kumari-anushka/trace",
        owner="kumari-anushka",
        name="trace",
    )


async def test_create_repository_creates_repository_and_ingestion(
    service: RepositoryCreationService,
) -> None:
    repository = make_repository()

    github_repository = MagicMock()
    github_repository.default_branch = "main"

    commit = MagicMock()
    commit.sha = "a" * 40

    parse_github_url_mock = MagicMock(
        return_value=(
            "https://github.com/kumari-anushka/trace",
            "kumari-anushka",
            "trace",
        ),
    )
    get_github_repository_mock = AsyncMock(
        return_value=github_repository,
    )
    create_repository_mock = AsyncMock(
        return_value=repository,
    )
    get_commit_mock = AsyncMock(
        return_value=commit,
    )
    create_ingestion_mock = AsyncMock()

    with (
        patch.object(
            service.repository_service,
            "parse_github_url",
            parse_github_url_mock,
        ),
        patch.object(
            service.github_client,
            "get_repository",
            get_github_repository_mock,
        ),
        patch.object(
            service.repository_service,
            "create_repository",
            create_repository_mock,
        ),
        patch.object(
            service.github_client,
            "get_commit",
            get_commit_mock,
        ),
        patch.object(
            service.ingestion_service,
            "create_ingestion",
            create_ingestion_mock,
        ),
    ):
        result = await service.create_repository(
            github_url=("https://www.github.com/kumari-anushka/trace.git/"),
        )

    assert result is repository

    parse_github_url_mock.assert_called_once_with(
        "https://www.github.com/kumari-anushka/trace.git/",
    )

    get_github_repository_mock.assert_awaited_once_with(
        owner="kumari-anushka",
        name="trace",
    )

    create_repository_mock.assert_awaited_once_with(
        github_url="https://github.com/kumari-anushka/trace",
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
        commit_sha="a" * 40,
        default_branch="main",
    )


async def test_create_repository_validates_github_before_saving(
    service: RepositoryCreationService,
) -> None:
    github_repository = MagicMock()
    github_repository.default_branch = "main"

    repository = make_repository()

    get_github_repository_mock = AsyncMock(
        return_value=github_repository,
    )
    create_repository_mock = AsyncMock(
        return_value=repository,
    )
    get_commit_mock = AsyncMock(
        return_value=MagicMock(sha="a" * 40),
    )
    create_ingestion_mock = AsyncMock()

    with (
        patch.object(
            service.github_client,
            "get_repository",
            get_github_repository_mock,
        ),
        patch.object(
            service.repository_service,
            "create_repository",
            create_repository_mock,
        ),
        patch.object(
            service.github_client,
            "get_commit",
            get_commit_mock,
        ),
        patch.object(
            service.ingestion_service,
            "create_ingestion",
            create_ingestion_mock,
        ),
    ):
        await service.create_repository(
            github_url="https://github.com/kumari-anushka/trace",
        )

    get_github_repository_mock.assert_awaited_once()
    create_repository_mock.assert_awaited_once()


async def test_create_repository_does_not_save_missing_github_repository(
    service: RepositoryCreationService,
) -> None:
    request = httpx.Request(
        method="GET",
        url=("https://api.github.com/repos/missing/repository"),
    )
    response = httpx.Response(
        status_code=404,
        request=request,
    )

    get_github_repository_mock = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            message="GitHub repository not found",
            request=request,
            response=response,
        ),
    )
    create_repository_mock = AsyncMock()
    get_commit_mock = AsyncMock()
    create_ingestion_mock = AsyncMock()

    with (
        patch.object(
            service.github_client,
            "get_repository",
            get_github_repository_mock,
        ),
        patch.object(
            service.repository_service,
            "create_repository",
            create_repository_mock,
        ),
        patch.object(
            service.github_client,
            "get_commit",
            get_commit_mock,
        ),
        patch.object(
            service.ingestion_service,
            "create_ingestion",
            create_ingestion_mock,
        ),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await service.create_repository(
                github_url=("https://github.com/missing/repository"),
            )

    get_github_repository_mock.assert_awaited_once_with(
        owner="missing",
        name="repository",
    )
    create_repository_mock.assert_not_awaited()
    get_commit_mock.assert_not_awaited()
    create_ingestion_mock.assert_not_awaited()


async def test_create_repository_does_not_save_when_github_times_out(
    service: RepositoryCreationService,
) -> None:
    request = httpx.Request(
        method="GET",
        url=("https://api.github.com/repos/kumari-anushka/trace"),
    )

    get_github_repository_mock = AsyncMock(
        side_effect=httpx.ReadTimeout(
            message="GitHub request timed out",
            request=request,
        ),
    )
    create_repository_mock = AsyncMock()
    get_commit_mock = AsyncMock()
    create_ingestion_mock = AsyncMock()

    with (
        patch.object(
            service.github_client,
            "get_repository",
            get_github_repository_mock,
        ),
        patch.object(
            service.repository_service,
            "create_repository",
            create_repository_mock,
        ),
        patch.object(
            service.github_client,
            "get_commit",
            get_commit_mock,
        ),
        patch.object(
            service.ingestion_service,
            "create_ingestion",
            create_ingestion_mock,
        ),
    ):
        with pytest.raises(httpx.ReadTimeout):
            await service.create_repository(
                github_url=("https://github.com/kumari-anushka/trace"),
            )

    create_repository_mock.assert_not_awaited()
    get_commit_mock.assert_not_awaited()
    create_ingestion_mock.assert_not_awaited()


async def test_create_repository_rejects_invalid_url_before_github_call(
    service: RepositoryCreationService,
) -> None:
    get_github_repository_mock = AsyncMock()
    create_repository_mock = AsyncMock()
    get_commit_mock = AsyncMock()
    create_ingestion_mock = AsyncMock()

    with (
        patch.object(
            service.github_client,
            "get_repository",
            get_github_repository_mock,
        ),
        patch.object(
            service.repository_service,
            "create_repository",
            create_repository_mock,
        ),
        patch.object(
            service.github_client,
            "get_commit",
            get_commit_mock,
        ),
        patch.object(
            service.ingestion_service,
            "create_ingestion",
            create_ingestion_mock,
        ),
    ):
        with pytest.raises(InvalidGitHubRepositoryURLError):
            await service.create_repository(
                github_url="https://gitlab.com/owner/repository",
            )

    get_github_repository_mock.assert_not_awaited()
    create_repository_mock.assert_not_awaited()
    get_commit_mock.assert_not_awaited()
    create_ingestion_mock.assert_not_awaited()


async def test_create_repository_fetches_commit_from_default_branch(
    service: RepositoryCreationService,
) -> None:
    repository = make_repository()

    github_repository = MagicMock()
    github_repository.default_branch = "develop"

    commit = MagicMock()
    commit.sha = "b" * 40

    get_github_repository_mock = AsyncMock(
        return_value=github_repository,
    )
    create_repository_mock = AsyncMock(
        return_value=repository,
    )
    get_commit_mock = AsyncMock(
        return_value=commit,
    )
    create_ingestion_mock = AsyncMock()

    with (
        patch.object(
            service.github_client,
            "get_repository",
            get_github_repository_mock,
        ),
        patch.object(
            service.repository_service,
            "create_repository",
            create_repository_mock,
        ),
        patch.object(
            service.github_client,
            "get_commit",
            get_commit_mock,
        ),
        patch.object(
            service.ingestion_service,
            "create_ingestion",
            create_ingestion_mock,
        ),
    ):
        await service.create_repository(
            github_url="https://github.com/kumari-anushka/trace",
        )

    get_commit_mock.assert_awaited_once_with(
        owner="kumari-anushka",
        name="trace",
        ref="develop",
    )

    create_ingestion_mock.assert_awaited_once_with(
        repository=repository,
        commit_sha="b" * 40,
        default_branch="develop",
    )


async def test_create_repository_does_not_create_ingestion_when_commit_fails(
    service: RepositoryCreationService,
) -> None:
    repository = make_repository()

    github_repository = MagicMock()
    github_repository.default_branch = "main"

    request = httpx.Request(
        method="GET",
        url=("https://api.github.com/repos/kumari-anushka/trace/commits/main"),
    )
    response = httpx.Response(
        status_code=500,
        request=request,
    )

    get_github_repository_mock = AsyncMock(
        return_value=github_repository,
    )
    create_repository_mock = AsyncMock(
        return_value=repository,
    )
    get_commit_mock = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            message="GitHub commit request failed",
            request=request,
            response=response,
        ),
    )
    create_ingestion_mock = AsyncMock()

    with (
        patch.object(
            service.github_client,
            "get_repository",
            get_github_repository_mock,
        ),
        patch.object(
            service.repository_service,
            "create_repository",
            create_repository_mock,
        ),
        patch.object(
            service.github_client,
            "get_commit",
            get_commit_mock,
        ),
        patch.object(
            service.ingestion_service,
            "create_ingestion",
            create_ingestion_mock,
        ),
    ):
        with pytest.raises(httpx.HTTPStatusError):
            await service.create_repository(
                github_url=("https://github.com/kumari-anushka/trace"),
            )

    create_repository_mock.assert_awaited_once()
    get_commit_mock.assert_awaited_once()
    create_ingestion_mock.assert_not_awaited()
