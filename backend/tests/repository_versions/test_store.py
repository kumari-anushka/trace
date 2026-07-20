from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.repository_versions.models import RepositoryVersion
from src.repository_versions.store import RepositoryVersionStore

COMMIT_SHA = "a" * 40


def make_repository_version(
    *,
    repository_version_id: UUID | None = None,
    repository_id: UUID | None = None,
    commit_sha: str = COMMIT_SHA,
) -> RepositoryVersion:
    repository_version = RepositoryVersion(
        repository_id=repository_id or uuid4(),
        commit_sha=commit_sha,
        branch="main",
    )

    repository_version.id = repository_version_id or uuid4()
    repository_version.created_at = datetime.now(UTC)

    return repository_version


def make_store() -> tuple[
    RepositoryVersionStore,
    AsyncMock,
]:
    session = AsyncMock(spec=AsyncSession)

    store = RepositoryVersionStore(
        session=session,
    )

    return store, session


@pytest.mark.asyncio
async def test_create_adds_and_flushes_repository_version() -> None:
    store, session = make_store()
    repository_id = uuid4()

    repository_version = await store.create(
        repository_id=repository_id,
        commit_sha=COMMIT_SHA,
        branch="main",
    )

    assert repository_version.repository_id == repository_id
    assert repository_version.commit_sha == COMMIT_SHA
    assert repository_version.branch == "main"

    session.add.assert_called_once_with(repository_version)
    session.flush.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_get_by_id_returns_repository_version() -> None:
    store, session = make_store()
    repository_version = make_repository_version()

    session.get.return_value = repository_version

    returned_version = await store.get_by_id(
        repository_version.id,
    )

    assert returned_version is repository_version

    session.get.assert_awaited_once_with(
        RepositoryVersion,
        repository_version.id,
    )


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_missing() -> None:
    store, session = make_store()
    repository_version_id = uuid4()

    session.get.return_value = None

    returned_version = await store.get_by_id(
        repository_version_id,
    )

    assert returned_version is None

    session.get.assert_awaited_once_with(
        RepositoryVersion,
        repository_version_id,
    )


@pytest.mark.asyncio
async def test_get_by_repository_and_commit_returns_version() -> None:
    store, session = make_store()
    repository_id = uuid4()

    repository_version = make_repository_version(
        repository_id=repository_id,
    )

    result = MagicMock()
    result.scalar_one_or_none.return_value = repository_version
    session.execute.return_value = result

    returned_version = await store.get_by_repository_and_commit(
        repository_id=repository_id,
        commit_sha=COMMIT_SHA,
    )

    assert returned_version is repository_version
    session.execute.assert_awaited_once()
    result.scalar_one_or_none.assert_called_once_with()


@pytest.mark.asyncio
async def test_get_by_repository_and_commit_returns_none() -> None:
    store, session = make_store()
    repository_id = uuid4()

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    returned_version = await store.get_by_repository_and_commit(
        repository_id=repository_id,
        commit_sha=COMMIT_SHA,
    )

    assert returned_version is None
    session.execute.assert_awaited_once()
    result.scalar_one_or_none.assert_called_once_with()


@pytest.mark.asyncio
async def test_list_by_repository_returns_versions() -> None:
    store, session = make_store()
    repository_id = uuid4()

    repository_versions = [
        make_repository_version(
            repository_id=repository_id,
            commit_sha="a" * 40,
        ),
        make_repository_version(
            repository_id=repository_id,
            commit_sha="b" * 40,
        ),
    ]

    scalar_result = MagicMock()
    scalar_result.all.return_value = repository_versions

    result = MagicMock()
    result.scalars.return_value = scalar_result
    session.execute.return_value = result

    returned_versions = await store.list_by_repository(
        repository_id,
    )

    assert returned_versions == repository_versions

    session.execute.assert_awaited_once()
    result.scalars.assert_called_once_with()
    scalar_result.all.assert_called_once_with()


@pytest.mark.asyncio
async def test_list_by_repository_returns_empty_list() -> None:
    store, session = make_store()

    scalar_result = MagicMock()
    scalar_result.all.return_value = []

    result = MagicMock()
    result.scalars.return_value = scalar_result
    session.execute.return_value = result

    returned_versions = await store.list_by_repository(
        uuid4(),
    )

    assert returned_versions == []

    session.execute.assert_awaited_once()
    result.scalars.assert_called_once_with()
    scalar_result.all.assert_called_once_with()
