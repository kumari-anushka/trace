from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from src.core.exceptions import (
    ActiveIngestionJobAlreadyExistsError,
    IngestionJobNotFoundError,
    InvalidIngestionJobTransitionError,
    InvalidIngestionProgressError,
)
from src.ingestion.models import (
    ACTIVE_INGESTION_JOB_INDEX_NAME,
    IngestionJob,
    IngestionJobStatus,
)
from src.ingestion.service import IngestionService
from src.ingestion.store import IngestionJobStore


class ConstraintDiagnostic:
    def __init__(self, constraint_name: str) -> None:
        self.constraint_name = constraint_name


class DatabaseConstraintError(Exception):
    def __init__(self, constraint_name: str) -> None:
        super().__init__(constraint_name)
        self.diag = ConstraintDiagnostic(constraint_name)


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

    return ingestion_job


def make_service() -> tuple[
    IngestionService,
    AsyncMock,
]:
    store = AsyncMock(spec=IngestionJobStore)

    store.flush.side_effect = lambda ingestion_job: ingestion_job
    store.get_active_by_repository_version.return_value = None

    service = IngestionService(
        store=store,
    )

    return service, store


@pytest.mark.asyncio
async def test_create_job_returns_created_job() -> None:
    service, store = make_service()
    repository_version_id = uuid4()
    ingestion_job = make_ingestion_job(
        repository_version_id=repository_version_id,
    )

    store.create.return_value = ingestion_job

    result = await service.create_job(
        repository_version_id=repository_version_id,
    )

    assert result is ingestion_job
    store.get_active_by_repository_version.assert_awaited_once_with(
        repository_version_id,
    )
    store.create.assert_awaited_once_with(
        repository_version_id=repository_version_id,
    )


@pytest.mark.asyncio
async def test_create_job_rejects_existing_active_job() -> None:
    service, store = make_service()
    repository_version_id = uuid4()
    active_job = make_ingestion_job(
        repository_version_id=repository_version_id,
        status=IngestionJobStatus.QUEUED,
    )
    store.get_active_by_repository_version.return_value = active_job

    with pytest.raises(
        ActiveIngestionJobAlreadyExistsError,
        match="An ingestion job is already active",
    ):
        await service.create_job(
            repository_version_id=repository_version_id,
        )

    store.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_job_maps_unique_index_race_to_domain_error() -> None:
    service, store = make_service()
    repository_version_id = uuid4()
    store.create.side_effect = IntegrityError(
        statement="INSERT",
        params={},
        orig=DatabaseConstraintError(
            ACTIVE_INGESTION_JOB_INDEX_NAME,
        ),
    )

    with pytest.raises(
        ActiveIngestionJobAlreadyExistsError,
        match="An ingestion job is already active",
    ):
        await service.create_job(
            repository_version_id=repository_version_id,
        )

    store.get_active_by_repository_version.assert_awaited_once_with(
        repository_version_id,
    )
    store.create.assert_awaited_once_with(
        repository_version_id=repository_version_id,
    )


@pytest.mark.asyncio
async def test_create_job_preserves_unrelated_integrity_error() -> None:
    service, store = make_service()
    repository_version_id = uuid4()
    integrity_error = IntegrityError(
        statement="INSERT",
        params={},
        orig=DatabaseConstraintError("some_other_constraint"),
    )
    store.create.side_effect = integrity_error

    with pytest.raises(IntegrityError) as raised_error:
        await service.create_job(
            repository_version_id=repository_version_id,
        )

    assert raised_error.value is integrity_error


@pytest.mark.asyncio
async def test_get_job_returns_job() -> None:
    service, store = make_service()
    ingestion_job = make_ingestion_job()

    store.get_by_id.return_value = ingestion_job

    result = await service.get_job(
        ingestion_job.id,
    )

    assert result is ingestion_job
    store.get_by_id.assert_awaited_once_with(
        ingestion_job.id,
    )


@pytest.mark.asyncio
async def test_get_job_raises_when_not_found() -> None:
    service, store = make_service()
    ingestion_job_id = uuid4()

    store.get_by_id.return_value = None

    with pytest.raises(
        IngestionJobNotFoundError,
        match="Ingestion job not found",
    ):
        await service.get_job(ingestion_job_id)

    store.get_by_id.assert_awaited_once_with(
        ingestion_job_id,
    )


@pytest.mark.asyncio
async def test_mark_queued_transitions_pending_job() -> None:
    service, store = make_service()
    ingestion_job = make_ingestion_job(
        status=IngestionJobStatus.PENDING,
    )

    result = await service.mark_queued(
        ingestion_job,
    )

    assert result is ingestion_job
    assert ingestion_job.status is IngestionJobStatus.QUEUED

    store.flush.assert_awaited_once_with(
        ingestion_job,
    )


@pytest.mark.asyncio
async def test_mark_running_transitions_queued_job() -> None:
    service, store = make_service()
    ingestion_job = make_ingestion_job(
        status=IngestionJobStatus.QUEUED,
    )
    ingestion_job.error_message = "Previous error"

    result = await service.mark_running(
        ingestion_job,
    )

    assert result is ingestion_job
    assert ingestion_job.status is IngestionJobStatus.RUNNING
    assert ingestion_job.started_at is not None
    assert ingestion_job.started_at.tzinfo is not None
    assert ingestion_job.error_message is None

    store.flush.assert_awaited_once_with(
        ingestion_job,
    )


@pytest.mark.asyncio
async def test_update_progress_updates_running_job() -> None:
    service, store = make_service()
    ingestion_job = make_ingestion_job(
        status=IngestionJobStatus.RUNNING,
        progress=10,
    )

    result = await service.update_progress(
        ingestion_job,
        progress=55,
    )

    assert result is ingestion_job
    assert ingestion_job.progress == 55

    store.flush.assert_awaited_once_with(
        ingestion_job,
    )


@pytest.mark.asyncio
async def test_update_progress_rejects_non_running_job() -> None:
    service, store = make_service()
    ingestion_job = make_ingestion_job(
        status=IngestionJobStatus.QUEUED,
    )

    with pytest.raises(
        InvalidIngestionJobTransitionError,
        match=("Progress can only be updated for a running ingestion job"),
    ):
        await service.update_progress(
            ingestion_job,
            progress=50,
        )

    store.flush.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "progress",
    [
        -1,
        100,
        101,
    ],
)
async def test_update_progress_rejects_invalid_progress(
    progress: int,
) -> None:
    service, store = make_service()
    ingestion_job = make_ingestion_job(
        status=IngestionJobStatus.RUNNING,
    )

    with pytest.raises(
        InvalidIngestionProgressError,
        match=("Running ingestion progress must be between 0 and 99"),
    ):
        await service.update_progress(
            ingestion_job,
            progress=progress,
        )

    store.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_mark_completed_transitions_running_job() -> None:
    service, store = make_service()
    ingestion_job = make_ingestion_job(
        status=IngestionJobStatus.RUNNING,
        progress=75,
    )
    ingestion_job.error_message = "Old error"

    result = await service.mark_completed(
        ingestion_job,
    )

    assert result is ingestion_job
    assert ingestion_job.status is IngestionJobStatus.COMPLETED
    assert ingestion_job.progress == 100
    assert ingestion_job.error_message is None
    assert ingestion_job.completed_at is not None
    assert ingestion_job.completed_at.tzinfo is not None

    store.flush.assert_awaited_once_with(
        ingestion_job,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        IngestionJobStatus.PENDING,
        IngestionJobStatus.QUEUED,
        IngestionJobStatus.RUNNING,
    ],
)
async def test_mark_failed_transitions_active_job(
    status: IngestionJobStatus,
) -> None:
    service, store = make_service()
    ingestion_job = make_ingestion_job(
        status=status,
    )

    result = await service.mark_failed(
        ingestion_job,
        error_message="Ingestion failed",
    )

    assert result is ingestion_job
    assert ingestion_job.status is IngestionJobStatus.FAILED
    assert ingestion_job.error_message == "Ingestion failed"
    assert ingestion_job.completed_at is not None
    assert ingestion_job.completed_at.tzinfo is not None

    store.flush.assert_awaited_once_with(
        ingestion_job,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("current_status", "operation"),
    [
        (
            IngestionJobStatus.COMPLETED,
            "mark_queued",
        ),
        (
            IngestionJobStatus.FAILED,
            "mark_queued",
        ),
        (
            IngestionJobStatus.PENDING,
            "mark_running",
        ),
        (
            IngestionJobStatus.QUEUED,
            "mark_completed",
        ),
        (
            IngestionJobStatus.COMPLETED,
            "mark_failed",
        ),
    ],
)
async def test_rejects_invalid_status_transition(
    current_status: IngestionJobStatus,
    operation: str,
) -> None:
    service, store = make_service()
    ingestion_job = make_ingestion_job(
        status=current_status,
    )

    with pytest.raises(
        InvalidIngestionJobTransitionError,
        match="Cannot transition ingestion job",
    ):
        if operation == "mark_queued":
            await service.mark_queued(ingestion_job)
        elif operation == "mark_running":
            await service.mark_running(ingestion_job)
        elif operation == "mark_completed":
            await service.mark_completed(ingestion_job)
        else:
            await service.mark_failed(
                ingestion_job,
                error_message="Failed",
            )

    store.flush.assert_not_awaited()
