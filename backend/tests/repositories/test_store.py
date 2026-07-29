from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.models import Repository
from src.repositories.store import RepositoryStore

GITHUB_URL = "https://github.com/kumari-anushka/trace"


def make_repository(
    *,
    repository_id: UUID | None = None,
    github_id: int = 123456789,
    github_url: str = GITHUB_URL,
) -> Repository:
    now = datetime.now(UTC)

    repository = Repository(
        github_id=github_id,
        github_url=github_url,
        owner="kumari-anushka",
        name="trace",
        default_branch="main",
    )

    repository.id = repository_id or uuid4()
    repository.created_at = now
    repository.updated_at = now

    return repository


def make_store() -> tuple[
    RepositoryStore,
    AsyncMock,
]:
    session = AsyncMock(spec=AsyncSession)

    store = RepositoryStore(
        session=session,
    )

    return store, session


@pytest.mark.asyncio
async def test_create_adds_and_flushes_repository() -> None:
    store, session = make_store()

    repository = await store.create(
        github_id=123456789,
        github_url=GITHUB_URL,
        owner="kumari-anushka",
        name="trace",
        default_branch="main",
    )

    assert repository.github_id == 123456789
    assert repository.github_url == GITHUB_URL
    assert repository.owner == "kumari-anushka"
    assert repository.name == "trace"
    assert repository.default_branch == "main"

    session.add.assert_called_once_with(repository)
    session.flush.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_get_by_id_returns_repository() -> None:
    store, session = make_store()
    repository = make_repository()

    session.get.return_value = repository

    returned_repository = await store.get_by_id(
        repository.id,
    )

    assert returned_repository is repository

    session.get.assert_awaited_once_with(
        Repository,
        repository.id,
    )


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_missing() -> None:
    store, session = make_store()
    repository_id = uuid4()

    session.get.return_value = None

    returned_repository = await store.get_by_id(
        repository_id,
    )

    assert returned_repository is None

    session.get.assert_awaited_once_with(
        Repository,
        repository_id,
    )


@pytest.mark.asyncio
async def test_get_by_github_id_returns_repository() -> None:
    store, session = make_store()
    repository = make_repository()

    result = MagicMock()
    result.scalar_one_or_none.return_value = repository
    session.execute.return_value = result

    returned_repository = await store.get_by_github_id(
        repository.github_id,
    )

    assert returned_repository is repository
    session.execute.assert_awaited_once()
    result.scalar_one_or_none.assert_called_once_with()


@pytest.mark.asyncio
async def test_get_by_github_url_returns_repository() -> None:
    store, session = make_store()
    repository = make_repository()

    result = MagicMock()
    result.scalar_one_or_none.return_value = repository
    session.execute.return_value = result

    returned_repository = await store.get_by_github_url(
        repository.github_url,
    )

    assert returned_repository is repository
    session.execute.assert_awaited_once()
    result.scalar_one_or_none.assert_called_once_with()


@pytest.mark.asyncio
async def test_list_all_returns_repositories() -> None:
    store, session = make_store()

    repositories = [
        make_repository(
            github_id=1,
            github_url="https://github.com/example/first",
        ),
        make_repository(
            github_id=2,
            github_url="https://github.com/example/second",
        ),
    ]

    scalar_result = MagicMock()
    scalar_result.all.return_value = repositories

    result = MagicMock()
    result.scalars.return_value = scalar_result
    session.execute.return_value = result

    returned_repositories = await store.list_all()

    assert returned_repositories == repositories

    session.execute.assert_awaited_once()
    result.scalars.assert_called_once_with()
    scalar_result.all.assert_called_once_with()


@pytest.mark.asyncio
async def test_list_all_returns_empty_list() -> None:
    store, session = make_store()

    scalar_result = MagicMock()
    scalar_result.all.return_value = []

    result = MagicMock()
    result.scalars.return_value = scalar_result
    session.execute.return_value = result

    returned_repositories = await store.list_all()

    assert returned_repositories == []


@pytest.mark.asyncio
async def test_delete_deletes_and_flushes_repository() -> None:
    store, session = make_store()
    repository = make_repository()

    await store.delete(repository)

    session.delete.assert_awaited_once_with(repository)
    session.flush.assert_awaited_once_with()
