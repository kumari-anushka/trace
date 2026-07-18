from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    IngestionJobNotFoundError,
    InvalidIngestionProgressError,
    InvalidIngestionTransitionError,
    RepositorySnapshotNotFoundError,
    SnapshotAlreadyExistsError,
)
from src.models.enums import IngestionJobStatus, SnapshotStatus
from src.models.ingestion_job import IngestionJob
from src.models.repository import Repository
from src.models.repository_snapshot import RepositorySnapshot
from src.services.ingestion_service import IngestionService


@pytest.fixture
def session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    return session


@pytest.fixture
def repository() -> Repository:
    return Repository(
        id=1,
        github_url="https://github.com/kumari-anushka/trace",
        owner="kumari-anushka",
        name="trace",
        default_branch="main",
    )


@pytest.fixture
def snapshot() -> RepositorySnapshot:
    return RepositorySnapshot(
        id=1,
        repository_id=1,
        commit_sha="a1b2c3d4e5f6",
        default_branch="main",
        status=SnapshotStatus.PENDING,
    )


@pytest.mark.asyncio
async def test_create_ingestion_creates_snapshot_and_job(
    session: AsyncMock,
    repository: Repository,
) -> None:
    service = IngestionService(session)

    async def assign_snapshot_id() -> None:
        snapshot = session.add.call_args_list[0].args[0]
        snapshot.id = 10

    session.flush.side_effect = assign_snapshot_id

    snapshot, job = await service.create_ingestion(
        repository,
        commit_sha="a1b2c3d4e5f6",
        default_branch="main",
    )

    assert snapshot.repository_id == repository.id
    assert snapshot.commit_sha == "a1b2c3d4e5f6"
    assert snapshot.default_branch == "main"
    assert snapshot.status == SnapshotStatus.PENDING

    assert job.repository_id == repository.id
    assert job.snapshot_id == snapshot.id
    assert job.status == IngestionJobStatus.PENDING
    assert job.progress == 0

    assert session.add.call_count == 2
    session.flush.assert_awaited_once()
    session.commit.assert_awaited_once()
    session.refresh.assert_any_await(snapshot)
    session.refresh.assert_any_await(job)
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_ingestion_raises_snapshot_already_exists(
    session: AsyncMock,
    repository: Repository,
) -> None:
    service = IngestionService(session)

    session.flush.side_effect = IntegrityError(
        statement=None,
        params=None,
        orig=Exception("duplicate snapshot"),
    )

    with pytest.raises(SnapshotAlreadyExistsError):
        await service.create_ingestion(
            repository,
            commit_sha="a1b2c3d4e5f6",
            default_branch="main",
        )

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_ingestion_rolls_back_unexpected_error(
    session: AsyncMock,
    repository: Repository,
) -> None:
    service = IngestionService(session)
    session.commit.side_effect = RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        await service.create_ingestion(
            repository,
            commit_sha="a1b2c3d4e5f6",
            default_branch="main",
        )

    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_ingestion_job_returns_job(
    session: AsyncMock,
) -> None:
    job = IngestionJob(
        id=1,
        repository_id=1,
        snapshot_id=1,
        status=IngestionJobStatus.PENDING,
        progress=0,
    )

    service = IngestionService(session)

    with patch.object(
        service.ingestion_job_store,
        "get_by_id",
        new=AsyncMock(return_value=job),
    ) as get_by_id_mock:
        result = await service.get_ingestion_job(
            repository_id=1,
            job_id=1,
        )

    assert result is job
    get_by_id_mock.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_get_ingestion_job_raises_when_job_missing(
    session: AsyncMock,
) -> None:
    service = IngestionService(session)

    with patch.object(
        service.ingestion_job_store,
        "get_by_id",
        new=AsyncMock(return_value=None),
    ) as get_by_id_mock:
        with pytest.raises(IngestionJobNotFoundError):
            await service.get_ingestion_job(
                repository_id=1,
                job_id=999,
            )

    get_by_id_mock.assert_awaited_once_with(999)


@pytest.mark.asyncio
async def test_get_ingestion_job_raises_when_job_belongs_to_other_repository(
    session: AsyncMock,
) -> None:
    job = IngestionJob(
        id=1,
        repository_id=2,
        snapshot_id=1,
        status=IngestionJobStatus.PENDING,
        progress=0,
    )

    service = IngestionService(session)

    with patch.object(
        service.ingestion_job_store,
        "get_by_id",
        new=AsyncMock(return_value=job),
    ) as get_by_id_mock:
        with pytest.raises(IngestionJobNotFoundError):
            await service.get_ingestion_job(
                repository_id=1,
                job_id=1,
            )

    get_by_id_mock.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_update_ingestion_job_marks_job_running(
    session: AsyncMock,
    snapshot: RepositorySnapshot,
) -> None:
    job = IngestionJob(
        id=1,
        repository_id=1,
        snapshot_id=snapshot.id,
        status=IngestionJobStatus.PENDING,
        progress=0,
        started_at=None,
    )

    service = IngestionService(session)

    with (
        patch.object(
            service.ingestion_job_store,
            "get_by_id",
            new=AsyncMock(return_value=job),
        ),
        patch.object(
            service.repository_snapshot_store,
            "get_by_id",
            new=AsyncMock(return_value=snapshot),
        ),
    ):
        result = await service.update_ingestion_job(
            job_id=1,
            status=IngestionJobStatus.RUNNING,
            progress=20,
        )

    assert result.status == IngestionJobStatus.RUNNING
    assert result.progress == 20
    assert result.started_at is not None
    assert snapshot.status == SnapshotStatus.PENDING


@pytest.mark.asyncio
async def test_update_ingestion_job_marks_job_completed(
    session: AsyncMock,
    snapshot: RepositorySnapshot,
) -> None:
    job = IngestionJob(
        id=1,
        repository_id=1,
        snapshot_id=snapshot.id,
        status=IngestionJobStatus.RUNNING,
        progress=80,
        started_at=datetime.now(UTC),
    )

    service = IngestionService(session)

    with (
        patch.object(
            service.ingestion_job_store,
            "get_by_id",
            new=AsyncMock(return_value=job),
        ),
        patch.object(
            service.repository_snapshot_store,
            "get_by_id",
            new=AsyncMock(return_value=snapshot),
        ),
    ):
        result = await service.update_ingestion_job(
            job_id=1,
            status=IngestionJobStatus.COMPLETED,
            progress=100,
        )

    assert result.status == IngestionJobStatus.COMPLETED
    assert snapshot.status == SnapshotStatus.READY
    assert result.completed_at is not None


@pytest.mark.asyncio
async def test_update_ingestion_job_marks_job_failed(
    session: AsyncMock,
    snapshot: RepositorySnapshot,
) -> None:
    job = IngestionJob(
        id=1,
        repository_id=1,
        snapshot_id=snapshot.id,
        status=IngestionJobStatus.RUNNING,
        progress=40,
    )

    service = IngestionService(session)

    with (
        patch.object(
            service.ingestion_job_store,
            "get_by_id",
            new=AsyncMock(return_value=job),
        ),
        patch.object(
            service.repository_snapshot_store,
            "get_by_id",
            new=AsyncMock(return_value=snapshot),
        ),
    ):
        result = await service.update_ingestion_job(
            job_id=1,
            status=IngestionJobStatus.FAILED,
            progress=40,
            error_message="GitHub clone failed",
        )

    assert result.status == IngestionJobStatus.FAILED
    assert snapshot.status == SnapshotStatus.FAILED
    assert result.error_message == "GitHub clone failed"


@pytest.mark.asyncio
async def test_update_ingestion_job_raises_when_snapshot_missing(
    session: AsyncMock,
) -> None:
    job = IngestionJob(
        id=1,
        repository_id=1,
        snapshot_id=999,
        status=IngestionJobStatus.PENDING,
        progress=0,
    )

    service = IngestionService(session)

    with (
        patch.object(
            service.ingestion_job_store,
            "get_by_id",
            new=AsyncMock(return_value=job),
        ),
        patch.object(
            service.repository_snapshot_store,
            "get_by_id",
            new=AsyncMock(return_value=None),
        ),
    ):
        with pytest.raises(RepositorySnapshotNotFoundError):
            await service.update_ingestion_job(
                job_id=1,
                status=IngestionJobStatus.RUNNING,
                progress=10,
            )

    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_ingestion_job_rolls_back_when_commit_fails(
    session: AsyncMock,
) -> None:
    job = IngestionJob(
        id=1,
        repository_id=1,
        snapshot_id=1,
        status=IngestionJobStatus.PENDING,
        progress=0,
    )

    session.commit.side_effect = RuntimeError("database unavailable")

    service = IngestionService(session)

    with patch.object(
        service.ingestion_job_store,
        "get_by_id",
        new=AsyncMock(return_value=job),
    ):
        with pytest.raises(RuntimeError, match="database unavailable"):
            await service.update_ingestion_job(
                job_id=1,
                status=IngestionJobStatus.RUNNING,
                progress=10,
            )

    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_ingestion_job_rejects_invalid_transition(
    session: AsyncMock,
) -> None:
    job = IngestionJob(
        id=1,
        repository_id=1,
        snapshot_id=1,
        status=IngestionJobStatus.COMPLETED,
        progress=100,
    )

    service = IngestionService(session)

    with patch.object(
        service.ingestion_job_store,
        "get_by_id",
        new=AsyncMock(return_value=job),
    ):
        with pytest.raises(
            InvalidIngestionTransitionError,
            match="Cannot transition ingestion job",
        ):
            await service.update_ingestion_job(
                job_id=1,
                status=IngestionJobStatus.RUNNING,
                progress=100,
            )

    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_ingestion_job_rejects_decreasing_progress(
    session: AsyncMock,
) -> None:
    job = IngestionJob(
        id=1,
        repository_id=1,
        snapshot_id=1,
        status=IngestionJobStatus.RUNNING,
        progress=60,
    )

    service = IngestionService(session)

    with patch.object(
        service.ingestion_job_store,
        "get_by_id",
        new=AsyncMock(return_value=job),
    ):
        with pytest.raises(
            InvalidIngestionProgressError,
            match="progress cannot decrease",
        ):
            await service.update_ingestion_job(
                job_id=1,
                status=IngestionJobStatus.RUNNING,
                progress=40,
            )

    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_ingestion_job_rejects_incomplete_completed_job(
    session: AsyncMock,
) -> None:
    job = IngestionJob(
        id=1,
        repository_id=1,
        snapshot_id=1,
        status=IngestionJobStatus.RUNNING,
        progress=80,
    )

    service = IngestionService(session)

    with patch.object(
        service.ingestion_job_store,
        "get_by_id",
        new=AsyncMock(return_value=job),
    ):
        with pytest.raises(
            InvalidIngestionProgressError,
            match="must have progress 100",
        ):
            await service.update_ingestion_job(
                job_id=1,
                status=IngestionJobStatus.COMPLETED,
                progress=90,
            )

    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_ingestion_job_rejects_failure_without_error_message(
    session: AsyncMock,
) -> None:
    job = IngestionJob(
        id=1,
        repository_id=1,
        snapshot_id=1,
        status=IngestionJobStatus.RUNNING,
        progress=40,
    )

    service = IngestionService(session)

    with patch.object(
        service.ingestion_job_store,
        "get_by_id",
        new=AsyncMock(return_value=job),
    ):
        with pytest.raises(
            InvalidIngestionProgressError,
            match="must include an error message",
        ):
            await service.update_ingestion_job(
                job_id=1,
                status=IngestionJobStatus.FAILED,
                progress=40,
            )

    session.commit.assert_not_awaited()
