from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import RepositoryVersionNotFoundError
from src.ingestion.models import (
    IngestionJob,
    IngestionJobStatus,
    IngestionStage,
    IngestionStageStatus,
)
from src.ingestion.processor import (
    FOUNDATION_STAGE_NAME,
    FoundationIngestionProcessor,
)
from src.ingestion.service import IngestionService, IngestionStageService
from src.repository_versions.service import RepositoryVersionService


def make_job() -> IngestionJob:
    now = datetime.now(UTC)
    ingestion_job = IngestionJob(
        repository_version_id=uuid4(),
        status=IngestionJobStatus.RUNNING,
        progress=0,
    )
    ingestion_job.id = uuid4()
    ingestion_job.created_at = now
    ingestion_job.updated_at = now

    return ingestion_job


def make_stage(
    ingestion_job: IngestionJob,
    *,
    status: IngestionStageStatus = IngestionStageStatus.PENDING,
) -> IngestionStage:
    now = datetime.now(UTC)
    ingestion_stage = IngestionStage(
        ingestion_job_id=ingestion_job.id,
        name=FOUNDATION_STAGE_NAME,
        position=0,
        status=status,
        progress=(100 if status is IngestionStageStatus.COMPLETED else 0),
    )
    ingestion_stage.id = uuid4()
    ingestion_stage.created_at = now
    ingestion_stage.updated_at = now

    return ingestion_stage


def make_processor() -> tuple[
    FoundationIngestionProcessor,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    session = AsyncMock(spec=AsyncSession)
    ingestion_service = AsyncMock(spec=IngestionService)
    stage_service = AsyncMock(spec=IngestionStageService)
    repository_version_service = AsyncMock(spec=RepositoryVersionService)

    def update_job_progress(
        ingestion_job: IngestionJob,
        *,
        progress: int,
    ) -> IngestionJob:
        ingestion_job.progress = progress
        return ingestion_job

    def mark_stage_running(ingestion_stage: IngestionStage) -> IngestionStage:
        ingestion_stage.status = IngestionStageStatus.RUNNING
        return ingestion_stage

    def mark_stage_completed(ingestion_stage: IngestionStage) -> IngestionStage:
        ingestion_stage.status = IngestionStageStatus.COMPLETED
        ingestion_stage.progress = 100
        return ingestion_stage

    def mark_stage_failed(
        ingestion_stage: IngestionStage,
        *,
        error_message: str,
    ) -> IngestionStage:
        ingestion_stage.status = IngestionStageStatus.FAILED
        ingestion_stage.error_message = error_message
        return ingestion_stage

    ingestion_service.update_progress.side_effect = update_job_progress
    stage_service.mark_running.side_effect = mark_stage_running
    stage_service.mark_completed.side_effect = mark_stage_completed
    stage_service.mark_failed.side_effect = mark_stage_failed

    processor = FoundationIngestionProcessor(
        session=session,
        ingestion_service=ingestion_service,
        stage_service=stage_service,
        repository_version_service=repository_version_service,
    )

    return (
        processor,
        session,
        ingestion_service,
        stage_service,
        repository_version_service,
    )


@pytest.mark.asyncio
async def test_process_creates_and_completes_foundation_stage() -> None:
    (
        processor,
        session,
        ingestion_service,
        stage_service,
        repository_version_service,
    ) = make_processor()
    ingestion_job = make_job()
    ingestion_stage = make_stage(ingestion_job)
    stage_service.list_stages.return_value = []
    stage_service.create_stage.return_value = ingestion_stage

    await processor.process(ingestion_job)

    stage_service.create_stage.assert_awaited_once_with(
        ingestion_job_id=ingestion_job.id,
        name=FOUNDATION_STAGE_NAME,
        position=0,
    )
    stage_service.mark_running.assert_awaited_once_with(ingestion_stage)
    repository_version_service.get_repository_version.assert_awaited_once_with(
        ingestion_job.repository_version_id,
    )
    stage_service.mark_completed.assert_awaited_once_with(ingestion_stage)
    assert ingestion_service.update_progress.await_args_list[0].kwargs["progress"] == 10
    assert ingestion_service.update_progress.await_args_list[1].kwargs["progress"] == 99
    assert session.commit.await_count == 2
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_resumes_completed_stage_idempotently() -> None:
    (
        processor,
        session,
        ingestion_service,
        stage_service,
        repository_version_service,
    ) = make_processor()
    ingestion_job = make_job()
    ingestion_stage = make_stage(
        ingestion_job,
        status=IngestionStageStatus.COMPLETED,
    )
    stage_service.list_stages.return_value = [ingestion_stage]

    await processor.process(ingestion_job)

    stage_service.create_stage.assert_not_awaited()
    stage_service.mark_running.assert_not_awaited()
    repository_version_service.get_repository_version.assert_not_awaited()
    ingestion_service.update_progress.assert_awaited_once_with(
        ingestion_job,
        progress=99,
    )
    session.commit.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_process_marks_stage_failed_when_snapshot_is_missing() -> None:
    (
        processor,
        session,
        _,
        stage_service,
        repository_version_service,
    ) = make_processor()
    ingestion_job = make_job()
    ingestion_stage = make_stage(ingestion_job)
    stage_service.list_stages.return_value = [ingestion_stage]
    stage_service.get_stage.return_value = ingestion_stage
    repository_version_service.get_repository_version.side_effect = RepositoryVersionNotFoundError()

    with pytest.raises(
        RepositoryVersionNotFoundError,
        match="Repository version not found",
    ):
        await processor.process(ingestion_job)

    stage_service.mark_failed.assert_awaited_once_with(
        ingestion_stage,
        error_message="Repository version not found",
    )
    assert session.commit.await_count == 2
    session.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_process_rejects_terminal_non_completed_stage() -> None:
    processor, session, _, stage_service, _ = make_processor()
    ingestion_job = make_job()
    ingestion_stage = make_stage(
        ingestion_job,
        status=IngestionStageStatus.FAILED,
    )
    stage_service.list_stages.return_value = [ingestion_stage]

    with pytest.raises(
        RuntimeError,
        match="Foundation stage cannot resume from failed",
    ):
        await processor.process(ingestion_job)

    session.commit.assert_not_awaited()
