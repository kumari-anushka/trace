from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.models import IngestionJob, IngestionJobStatus
from src.ingestion.store import IngestionJobStore


def make_ingestion_job(
    *,
    ingestion_job_id: UUID | None = None,
    repository_version_id: UUID | None = None,
    status: IngestionJobStatus = IngestionJobStatus.PENDING,
    progress: int = 0,
) -> IngestionJob:
    now = datetime.now(UTC)

    ingestion_job = IngestionJob(
        repository_version_id=repository_version_id or uuid4(),
        status=status,
        progress=progress,
    )

    ingestion_job.id = ingestion_job_id or uuid4()
    ingestion_job.created_at = now
    ingestion_job.updated_at = now
    ingestion_job.started_at = None
    ingestion_job.completed_at = None
    ingestion_job.error_message = None

    return ingestion_job


def make_store() -> tuple[
    IngestionJobStore,
    AsyncMock,
]:
    session = AsyncMock(spec=AsyncSession)

    store = IngestionJobStore(
        session=session,
    )

    return store, session


@pytest.mark.asyncio
async def test_create_adds_and_flushes_ingestion_job() -> None:
    store, session = make_store()
    repository_version_id = uuid4()

    ingestion_job = await store.create(
        repository_version_id=repository_version_id,
    )

    assert ingestion_job.repository_version_id == (repository_version_id)
    assert ingestion_job.status is IngestionJobStatus.PENDING
    assert ingestion_job.progress == 0

    session.add.assert_called_once_with(ingestion_job)
    session.flush.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_get_by_id_returns_ingestion_job() -> None:
    store, session = make_store()
    ingestion_job = make_ingestion_job()

    session.get.return_value = ingestion_job

    returned_job = await store.get_by_id(
        ingestion_job.id,
    )

    assert returned_job is ingestion_job

    session.get.assert_awaited_once_with(
        IngestionJob,
        ingestion_job.id,
    )


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_missing() -> None:
    store, session = make_store()
    ingestion_job_id = uuid4()

    session.get.return_value = None

    returned_job = await store.get_by_id(
        ingestion_job_id,
    )

    assert returned_job is None

    session.get.assert_awaited_once_with(
        IngestionJob,
        ingestion_job_id,
    )


@pytest.mark.asyncio
async def test_list_by_repository_version_returns_jobs() -> None:
    store, session = make_store()
    repository_version_id = uuid4()

    ingestion_jobs = [
        make_ingestion_job(
            repository_version_id=repository_version_id,
            status=IngestionJobStatus.RUNNING,
            progress=40,
        ),
        make_ingestion_job(
            repository_version_id=repository_version_id,
            status=IngestionJobStatus.FAILED,
            progress=20,
        ),
    ]

    scalar_result = MagicMock()
    scalar_result.all.return_value = ingestion_jobs

    result = MagicMock()
    result.scalars.return_value = scalar_result

    session.execute.return_value = result

    returned_jobs = await store.list_by_repository_version(
        repository_version_id,
    )

    assert returned_jobs == ingestion_jobs

    session.execute.assert_awaited_once()
    result.scalars.assert_called_once_with()
    scalar_result.all.assert_called_once_with()


@pytest.mark.asyncio
async def test_list_by_repository_version_returns_empty_list() -> None:
    store, session = make_store()

    scalar_result = MagicMock()
    scalar_result.all.return_value = []

    result = MagicMock()
    result.scalars.return_value = scalar_result

    session.execute.return_value = result

    returned_jobs = await store.list_by_repository_version(
        uuid4(),
    )

    assert returned_jobs == []

    session.execute.assert_awaited_once()
    result.scalars.assert_called_once_with()
    scalar_result.all.assert_called_once_with()


@pytest.mark.asyncio
async def test_flush_flushes_and_returns_ingestion_job() -> None:
    store, session = make_store()
    ingestion_job = make_ingestion_job(
        status=IngestionJobStatus.RUNNING,
        progress=50,
    )

    returned_job = await store.flush(
        ingestion_job,
    )

    assert returned_job is ingestion_job
    session.flush.assert_awaited_once_with()
