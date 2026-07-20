from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.core.exceptions import RepositoryVersionNotFoundError
from src.repository_versions.models import RepositoryVersion
from src.repository_versions.service import RepositoryVersionService
from src.repository_versions.store import RepositoryVersionStore


def make_repository_version(
    *,
    repository_version_id: UUID | None = None,
    repository_id: UUID | None = None,
    commit_sha: str | None = None,
) -> RepositoryVersion:
    repository_version = RepositoryVersion(
        repository_id=repository_id or uuid4(),
        commit_sha=commit_sha or ("a" * 40),
        branch="main",
    )

    repository_version.id = repository_version_id or uuid4()
    repository_version.created_at = datetime.now(UTC)

    return repository_version


def make_service() -> tuple[
    RepositoryVersionService,
    AsyncMock,
]:
    store = AsyncMock(spec=RepositoryVersionStore)

    service = RepositoryVersionService(
        store=store,
    )

    return service, store


@pytest.mark.asyncio
async def test_get_repository_version_returns_version() -> None:
    service, store = make_service()
    repository_version = make_repository_version()

    store.get_by_id.return_value = repository_version

    result = await service.get_repository_version(
        repository_version.id,
    )

    assert result is repository_version
    store.get_by_id.assert_awaited_once_with(
        repository_version.id,
    )


@pytest.mark.asyncio
async def test_get_repository_version_raises_when_not_found() -> None:
    service, store = make_service()
    repository_version_id = uuid4()

    store.get_by_id.return_value = None

    with pytest.raises(
        RepositoryVersionNotFoundError,
        match="Repository version not found",
    ):
        await service.get_repository_version(
            repository_version_id,
        )

    store.get_by_id.assert_awaited_once_with(
        repository_version_id,
    )


@pytest.mark.asyncio
async def test_list_repository_versions_returns_versions() -> None:
    service, store = make_service()
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

    store.list_by_repository.return_value = repository_versions

    result = await service.list_repository_versions(
        repository_id,
    )

    assert result == repository_versions
    store.list_by_repository.assert_awaited_once_with(
        repository_id,
    )


@pytest.mark.asyncio
async def test_list_repository_versions_returns_empty_sequence() -> None:
    service, store = make_service()
    repository_id = uuid4()

    store.list_by_repository.return_value = []

    result = await service.list_repository_versions(
        repository_id,
    )

    assert result == []
    store.list_by_repository.assert_awaited_once_with(
        repository_id,
    )
