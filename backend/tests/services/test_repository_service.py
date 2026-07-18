from unittest.mock import AsyncMock, patch

import pytest

from src.core.exceptions import (
    InvalidGitHubRepositoryURLError,
    RepositoryAlreadyExistsError,
    RepositoryNotFoundError,
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
        )

    assert result is created_repository

    get_by_github_url_mock.assert_awaited_once_with(
        "https://github.com/kumari-anushka/trace",
    )

    create_mock.assert_awaited_once_with(
        github_url="https://github.com/kumari-anushka/trace",
        owner="kumari-anushka",
        name="trace",
    )


async def test_create_repository_rejects_non_github_url(
    service: RepositoryService,
) -> None:
    with pytest.raises(InvalidGitHubRepositoryURLError):
        await service.create_repository(
            github_url="https://gitlab.com/kumari-anushka/trace",
        )


async def test_create_repository_rejects_invalid_path(
    service: RepositoryService,
) -> None:
    with pytest.raises(InvalidGitHubRepositoryURLError):
        await service.create_repository(
            github_url="https://github.com/kumari-anushka",
        )


async def test_create_repository_rejects_duplicate(
    service: RepositoryService,
) -> None:
    existing_repository = Repository(
        id=1,
        github_url="https://github.com/kumari-anushka/trace",
        owner="kumari-anushka",
        name="trace",
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
            )

    get_by_github_url_mock.assert_awaited_once_with(
        "https://github.com/kumari-anushka/trace",
    )
    create_mock.assert_not_awaited()


async def test_list_repositories_returns_all_repositories(
    service: RepositoryService,
) -> None:
    repositories = [
        Repository(
            id=2,
            github_url="https://github.com/fastapi/fastapi",
            owner="fastapi",
            name="fastapi",
        ),
        Repository(
            id=1,
            github_url="https://github.com/kumari-anushka/trace",
            owner="kumari-anushka",
            name="trace",
        ),
    ]
    list_all_mock = AsyncMock(return_value=repositories)

    with patch.object(
        service.repository_store,
        "list_all",
        list_all_mock,
    ):
        result = await service.list_repositories()

    assert result == repositories
    list_all_mock.assert_awaited_once_with()


async def test_list_repositories_returns_empty_list(
    service: RepositoryService,
) -> None:
    list_all_mock = AsyncMock(return_value=[])

    with patch.object(
        service.repository_store,
        "list_all",
        list_all_mock,
    ):
        result = await service.list_repositories()

    assert result == []
    list_all_mock.assert_awaited_once_with()


async def test_delete_repository_deletes_existing_repository(
    service: RepositoryService,
) -> None:
    repository = Repository(
        id=1,
        github_url="https://github.com/kumari-anushka/trace",
        owner="kumari-anushka",
        name="trace",
    )
    get_by_id_mock = AsyncMock(return_value=repository)
    delete_mock = AsyncMock()

    with (
        patch.object(
            service.repository_store,
            "get_by_id",
            get_by_id_mock,
        ),
        patch.object(
            service.repository_store,
            "delete",
            delete_mock,
        ),
    ):
        await service.delete_repository(1)

    get_by_id_mock.assert_awaited_once_with(1)
    delete_mock.assert_awaited_once_with(repository)


async def test_delete_repository_rejects_missing_repository(
    service: RepositoryService,
) -> None:
    get_by_id_mock = AsyncMock(return_value=None)
    delete_mock = AsyncMock()

    with (
        patch.object(
            service.repository_store,
            "get_by_id",
            get_by_id_mock,
        ),
        patch.object(
            service.repository_store,
            "delete",
            delete_mock,
        ),
    ):
        with pytest.raises(RepositoryNotFoundError):
            await service.delete_repository(999)

    get_by_id_mock.assert_awaited_once_with(999)
    delete_mock.assert_not_awaited()
