from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import RepositoryNotFoundError
from src.repositories.models import Repository
from src.repositories.service import RepositoryService
from src.repositories.store import RepositoryStore


def make_repository(
    *,
    repository_id: UUID | None = None,
) -> Repository:
    now = datetime.now(UTC)

    repository = Repository(
        github_id=123456789,
        github_url="https://github.com/kumari-anushka/trace",
        owner="kumari-anushka",
        name="trace",
        default_branch="main",
    )

    repository.id = repository_id or uuid4()
    repository.created_at = now
    repository.updated_at = now

    return repository


def make_service() -> tuple[
    RepositoryService,
    AsyncMock,
    AsyncMock,
]:
    session = AsyncMock(spec=AsyncSession)
    store = AsyncMock(spec=RepositoryStore)

    service = RepositoryService(
        session=session,
        store=store,
    )

    return service, session, store


@pytest.mark.asyncio
async def test_get_repository_returns_repository() -> None:
    service, _, store = make_service()
    repository = make_repository()

    store.get_by_id.return_value = repository

    result = await service.get_repository(repository.id)

    assert result is repository
    store.get_by_id.assert_awaited_once_with(repository.id)


@pytest.mark.asyncio
async def test_get_repository_raises_when_not_found() -> None:
    service, _, store = make_service()
    repository_id = uuid4()

    store.get_by_id.return_value = None

    with pytest.raises(
        RepositoryNotFoundError,
        match="Repository not found",
    ):
        await service.get_repository(repository_id)

    store.get_by_id.assert_awaited_once_with(repository_id)


@pytest.mark.asyncio
async def test_list_repositories_returns_repositories() -> None:
    service, _, store = make_service()

    repositories = [
        make_repository(),
        make_repository(),
    ]

    store.list_all.return_value = repositories

    result = await service.list_repositories()

    assert result == repositories
    store.list_all.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_list_repositories_returns_empty_sequence() -> None:
    service, _, store = make_service()

    store.list_all.return_value = []

    result = await service.list_repositories()

    assert result == []
    store.list_all.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_delete_repository_deletes_and_commits() -> None:
    service, session, store = make_service()
    repository = make_repository()

    store.get_by_id.return_value = repository

    await service.delete_repository(repository.id)

    store.get_by_id.assert_awaited_once_with(repository.id)
    store.delete.assert_awaited_once_with(repository)
    session.commit.assert_awaited_once_with()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_repository_raises_when_not_found() -> None:
    service, session, store = make_service()
    repository_id = uuid4()

    store.get_by_id.return_value = None

    with pytest.raises(
        RepositoryNotFoundError,
        match="Repository not found",
    ):
        await service.delete_repository(repository_id)

    store.get_by_id.assert_awaited_once_with(repository_id)
    store.delete.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_repository_rolls_back_when_delete_fails() -> None:
    service, session, store = make_service()
    repository = make_repository()
    error = RuntimeError("Delete failed")

    store.get_by_id.return_value = repository
    store.delete.side_effect = error

    with pytest.raises(
        RuntimeError,
        match="Delete failed",
    ):
        await service.delete_repository(repository.id)

    store.delete.assert_awaited_once_with(repository)
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_delete_repository_rolls_back_when_commit_fails() -> None:
    service, session, store = make_service()
    repository = make_repository()
    error = RuntimeError("Commit failed")

    store.get_by_id.return_value = repository
    session.commit.side_effect = error

    with pytest.raises(
        RuntimeError,
        match="Commit failed",
    ):
        await service.delete_repository(repository.id)

    store.delete.assert_awaited_once_with(repository)
    session.commit.assert_awaited_once_with()
    session.rollback.assert_awaited_once_with()
