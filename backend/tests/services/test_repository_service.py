from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    InvalidGitHubRepositoryURLError,
    RepositoryAlreadyExistsError,
    RepositoryNotFoundError,
)
from src.models.repository import Repository
from src.services.repository_service import RepositoryService


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def service(
    session: AsyncMock,
) -> RepositoryService:
    return RepositoryService(session)


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
    )


async def test_create_repository_returns_created_repository(
    service: RepositoryService,
) -> None:
    repository = make_repository()

    get_by_github_url_mock = AsyncMock(return_value=None)
    create_mock = AsyncMock(return_value=repository)

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
            github_url="https://github.com/kumari-anushka/trace",
            owner="kumari-anushka",
            name="trace",
        )

    assert result is repository

    get_by_github_url_mock.assert_awaited_once_with(
        "https://github.com/kumari-anushka/trace",
    )

    create_mock.assert_awaited_once_with(
        github_url="https://github.com/kumari-anushka/trace",
        owner="kumari-anushka",
        name="trace",
    )


async def test_create_repository_rejects_existing_repository(
    service: RepositoryService,
) -> None:
    existing_repository = make_repository()

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
                owner="kumari-anushka",
                name="trace",
            )

    get_by_github_url_mock.assert_awaited_once_with(
        "https://github.com/kumari-anushka/trace",
    )
    create_mock.assert_not_awaited()


async def test_create_repository_handles_database_duplicate(
    service: RepositoryService,
    session: AsyncMock,
) -> None:
    get_by_github_url_mock = AsyncMock(return_value=None)
    create_mock = AsyncMock(
        side_effect=IntegrityError(
            statement=None,
            params=None,
            orig=Exception("duplicate repository"),
        ),
    )

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
                owner="kumari-anushka",
                name="trace",
            )

    create_mock.assert_awaited_once_with(
        github_url="https://github.com/kumari-anushka/trace",
        owner="kumari-anushka",
        name="trace",
    )
    session.rollback.assert_awaited_once_with()


async def test_get_repository_returns_existing_repository(
    service: RepositoryService,
) -> None:
    repository = make_repository()
    get_by_id_mock = AsyncMock(return_value=repository)

    with patch.object(
        service.repository_store,
        "get_by_id",
        get_by_id_mock,
    ):
        result = await service.get_repository(1)

    assert result is repository
    get_by_id_mock.assert_awaited_once_with(1)


async def test_get_repository_returns_none_when_missing(
    service: RepositoryService,
) -> None:
    get_by_id_mock = AsyncMock(return_value=None)

    with patch.object(
        service.repository_store,
        "get_by_id",
        get_by_id_mock,
    ):
        result = await service.get_repository(999)

    assert result is None
    get_by_id_mock.assert_awaited_once_with(999)


async def test_list_repositories_returns_all_repositories(
    service: RepositoryService,
) -> None:
    repositories = [
        make_repository(
            repository_id=2,
            github_url="https://github.com/fastapi/fastapi",
            owner="fastapi",
            name="fastapi",
        ),
        make_repository(),
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
    repository = make_repository()

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


def test_parse_github_url_normalizes_url() -> None:
    result = RepositoryService.parse_github_url(
        "https://www.github.com/kumari-anushka/trace.git/",
    )

    assert result == (
        "https://github.com/kumari-anushka/trace",
        "kumari-anushka",
        "trace",
    )


@pytest.mark.parametrize(
    "github_url",
    [
        "http://github.com/kumari-anushka/trace",
        "https://gitlab.com/kumari-anushka/trace",
        "https://github.com/kumari-anushka",
        "https://github.com/kumari-anushka/trace/issues",
        "not-a-url",
    ],
)
def test_parse_github_url_rejects_invalid_url(
    github_url: str,
) -> None:
    with pytest.raises(InvalidGitHubRepositoryURLError):
        RepositoryService.parse_github_url(github_url)
