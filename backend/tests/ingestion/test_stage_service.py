from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.exceptions import (
    IngestionStageNotFoundError,
    InvalidIngestionStageProgressError,
    InvalidIngestionStageTransitionError,
)
from src.ingestion.models import IngestionStage, IngestionStageStatus
from src.ingestion.service import IngestionStageService
from src.ingestion.store import IngestionStageStore


def make_stage(
    *,
    status: IngestionStageStatus = IngestionStageStatus.PENDING,
    progress: int = 0,
) -> IngestionStage:
    now = datetime.now(UTC)
    ingestion_stage = IngestionStage(
        ingestion_job_id=uuid4(),
        name="prepare_repository_snapshot",
        position=0,
        status=status,
        progress=progress,
    )
    ingestion_stage.id = uuid4()
    ingestion_stage.created_at = now
    ingestion_stage.updated_at = now

    return ingestion_stage


def make_service() -> tuple[IngestionStageService, AsyncMock]:
    store = AsyncMock(spec=IngestionStageStore)
    store.flush.side_effect = lambda ingestion_stage: ingestion_stage

    return IngestionStageService(store=store), store


@pytest.mark.asyncio
async def test_create_stage_delegates_to_store() -> None:
    service, store = make_service()
    ingestion_job_id = uuid4()
    ingestion_stage = make_stage()
    ingestion_stage.ingestion_job_id = ingestion_job_id
    store.create.return_value = ingestion_stage

    returned_stage = await service.create_stage(
        ingestion_job_id=ingestion_job_id,
        name="prepare_repository_snapshot",
        position=0,
    )

    assert returned_stage is ingestion_stage
    store.create.assert_awaited_once_with(
        ingestion_job_id=ingestion_job_id,
        name="prepare_repository_snapshot",
        position=0,
    )


@pytest.mark.asyncio
async def test_get_stage_raises_when_missing() -> None:
    service, store = make_service()
    ingestion_stage_id = uuid4()
    store.get_by_id.return_value = None

    with pytest.raises(
        IngestionStageNotFoundError,
        match="Ingestion stage not found",
    ):
        await service.get_stage(ingestion_stage_id)


@pytest.mark.asyncio
async def test_mark_running_starts_pending_stage() -> None:
    service, store = make_service()
    ingestion_stage = make_stage()

    returned_stage = await service.mark_running(ingestion_stage)

    assert returned_stage is ingestion_stage
    assert ingestion_stage.status is IngestionStageStatus.RUNNING
    assert ingestion_stage.started_at is not None
    assert ingestion_stage.started_at.tzinfo is not None
    store.flush.assert_awaited_once_with(ingestion_stage)


@pytest.mark.asyncio
async def test_update_progress_updates_running_stage() -> None:
    service, store = make_service()
    ingestion_stage = make_stage(
        status=IngestionStageStatus.RUNNING,
        progress=10,
    )

    await service.update_progress(
        ingestion_stage,
        progress=50,
    )

    assert ingestion_stage.progress == 50
    store.flush.assert_awaited_once_with(ingestion_stage)


@pytest.mark.asyncio
@pytest.mark.parametrize("progress", [-1, 100, 101])
async def test_update_progress_rejects_invalid_value(progress: int) -> None:
    service, store = make_service()
    ingestion_stage = make_stage(
        status=IngestionStageStatus.RUNNING,
    )

    with pytest.raises(InvalidIngestionStageProgressError):
        await service.update_progress(
            ingestion_stage,
            progress=progress,
        )

    store.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_mark_completed_finishes_running_stage() -> None:
    service, store = make_service()
    ingestion_stage = make_stage(
        status=IngestionStageStatus.RUNNING,
        progress=70,
    )

    await service.mark_completed(ingestion_stage)

    assert ingestion_stage.status is IngestionStageStatus.COMPLETED
    assert ingestion_stage.progress == 100
    assert ingestion_stage.completed_at is not None
    assert ingestion_stage.completed_at.tzinfo is not None
    store.flush.assert_awaited_once_with(ingestion_stage)


@pytest.mark.asyncio
async def test_mark_failed_records_error() -> None:
    service, store = make_service()
    ingestion_stage = make_stage(
        status=IngestionStageStatus.RUNNING,
    )

    await service.mark_failed(
        ingestion_stage,
        error_message="Snapshot is missing",
    )

    assert ingestion_stage.status is IngestionStageStatus.FAILED
    assert ingestion_stage.error_message == "Snapshot is missing"
    assert ingestion_stage.completed_at is not None
    store.flush.assert_awaited_once_with(ingestion_stage)


@pytest.mark.asyncio
async def test_mark_skipped_finishes_pending_stage() -> None:
    service, store = make_service()
    ingestion_stage = make_stage()

    await service.mark_skipped(ingestion_stage)

    assert ingestion_stage.status is IngestionStageStatus.SKIPPED
    assert ingestion_stage.completed_at is not None
    store.flush.assert_awaited_once_with(ingestion_stage)


@pytest.mark.asyncio
async def test_rejects_invalid_stage_transition() -> None:
    service, store = make_service()
    ingestion_stage = make_stage(
        status=IngestionStageStatus.COMPLETED,
        progress=100,
    )

    with pytest.raises(
        InvalidIngestionStageTransitionError,
        match="Cannot transition ingestion stage",
    ):
        await service.mark_running(ingestion_stage)

    store.flush.assert_not_awaited()
