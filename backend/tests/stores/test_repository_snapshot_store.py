from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.repository_snapshot import RepositorySnapshot
from src.stores.repository_snapshot_store import RepositorySnapshotStore


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.mark.asyncio
async def test_get_by_id_returns_snapshot(
    session: AsyncMock,
) -> None:
    snapshot = RepositorySnapshot(
        id=1,
        repository_id=1,
        commit_sha="a1b2c3d4e5f6",
        default_branch="main",
    )

    session.get.return_value = snapshot

    store = RepositorySnapshotStore(session)

    result = await store.get_by_id(1)

    assert result is snapshot
    session.get.assert_awaited_once_with(
        RepositorySnapshot,
        1,
    )


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_snapshot_missing(
    session: AsyncMock,
) -> None:
    session.get.return_value = None

    store = RepositorySnapshotStore(session)

    result = await store.get_by_id(999)

    assert result is None
    session.get.assert_awaited_once_with(
        RepositorySnapshot,
        999,
    )
