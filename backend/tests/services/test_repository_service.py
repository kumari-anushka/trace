from unittest.mock import AsyncMock, patch

import pytest

from src.core.exceptions import (
    InvalidGitHubRepositoryURLError,
    RepositoryAlreadyExistsError,
)
from src.models.repository import Repository
from src.services.repository_service import RepositoryService


@pytest.fixture
def service() -> RepositoryService:
    session = AsyncMock()
    return RepositoryService(session)


async def test_create_repository_normalizes_github_url(
    service: RepositoryService,
) -> None:
    created_repository = Repository(
        id=1,
        github_url="https://github.com/kumari-anushka/trace",
        owner="kumari-anushka",
        name="trace",
        default_branch="main",
    )

    get_by_github_url_mock = AsyncMock(return_value=None)
    create_mock = AsyncMock(return_value=created_repository)

    with (
        patch.object(
            service.repository_store,
            "get_by_github_url",
            get_by_github_url_mock,
        ),
        patch.object(
            service.repository_store,
            "create",
            create_mock,
        ),
    ):
        result = await service.create_repository(
            github_url="https://www.github.com/kumari-anushka/trace.git/",
            default_branch="main",
        )

    assert result is created_repository

    get_by_github_url_mock.assert_awaited_once_with(
        "https://github.com/kumari-anushka/trace",
    )

    create_mock.assert_awaited_once_with(
        github_url="https://github.com/kumari-anushka/trace",
        owner="kumari-anushka",
        name="trace",
        default_branch="main",
    )


async def test_create_repository_strips_default_branch(
    service: RepositoryService,
) -> None:
    created_repository = Repository(
        id=1,
        github_url="https://github.com/kumari-anushka/trace",
        owner="kumari-anushka",
        name="trace",
        default_branch="main",
    )

    get_by_github_url_mock = AsyncMock(return_value=None)
    create_mock = AsyncMock(return_value=created_repository)

    with (
        patch.object(
            service.repository_store,
            "get_by_github_url",
            get_by_github_url_mock,
        ),
        patch.object(
            service.repository_store,
            "create",
            create_mock,
        ),
    ):
        await service.create_repository(
            github_url="https://github.com/kumari-anushka/trace",
            default_branch="  main  ",
        )

    create_mock.assert_awaited_once_with(
        github_url="https://github.com/kumari-anushka/trace",
        owner="kumari-anushka",
        name="trace",
        default_branch="main",
    )


async def test_create_repository_rejects_non_github_url(
    service: RepositoryService,
) -> None:
    with pytest.raises(InvalidGitHubRepositoryURLError):
        await service.create_repository(
            github_url="https://gitlab.com/kumari-anushka/trace",
            default_branch="main",
        )


async def test_create_repository_rejects_invalid_path(
    service: RepositoryService,
) -> None:
    with pytest.raises(InvalidGitHubRepositoryURLError):
        await service.create_repository(
            github_url="https://github.com/kumari-anushka",
            default_branch="main",
        )


async def test_create_repository_rejects_duplicate(
    service: RepositoryService,
) -> None:
    existing_repository = Repository(
        id=1,
        github_url="https://github.com/kumari-anushka/trace",
        owner="kumari-anushka",
        name="trace",
        default_branch="main",
    )

    get_by_github_url_mock = AsyncMock(
        return_value=existing_repository,
    )
    create_mock = AsyncMock()

    with (
        patch.object(
            service.repository_store,
            "get_by_github_url",
            get_by_github_url_mock,
        ),
        patch.object(
            service.repository_store,
            "create",
            create_mock,
        ),
    ):
        with pytest.raises(RepositoryAlreadyExistsError):
            await service.create_repository(
                github_url="https://github.com/kumari-anushka/trace",
                default_branch="main",
            )

    get_by_github_url_mock.assert_awaited_once_with(
        "https://github.com/kumari-anushka/trace",
    )
    create_mock.assert_not_awaited()
