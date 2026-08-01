from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import IngestionJobNotFoundError
from src.ingestion.models import IngestionJob, IngestionJobStatus
from src.ingestion.queue import (
    IngestionConsumer,
    IngestionMessage,
    InvalidIngestionMessageError,
)
from src.ingestion.runner import IngestionJobProcessor, IngestionWorker
from src.ingestion.service import IngestionService


def make_ingestion_job(
    *,
    status: IngestionJobStatus = IngestionJobStatus.QUEUED,
) -> IngestionJob:
    now = datetime.now(UTC)
    ingestion_job = IngestionJob(
        repository_version_id=uuid4(),
        status=status,
        progress=0,
    )
    ingestion_job.id = uuid4()
    ingestion_job.created_at = now
    ingestion_job.updated_at = now

    return ingestion_job


def make_message(
    ingestion_job_id: UUID,
) -> IngestionMessage:
    return IngestionMessage(
        entry_id="123-0",
        ingestion_job_id=ingestion_job_id,
    )


def make_worker() -> tuple[
    IngestionWorker,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    session = AsyncMock(spec=AsyncSession)
    consumer = AsyncMock(spec=IngestionConsumer)
    ingestion_service = AsyncMock(spec=IngestionService)
    processor = AsyncMock(spec=IngestionJobProcessor)

    def mark_queued(ingestion_job: IngestionJob) -> IngestionJob:
        ingestion_job.status = IngestionJobStatus.QUEUED
        return ingestion_job

    def mark_running(ingestion_job: IngestionJob) -> IngestionJob:
        ingestion_job.status = IngestionJobStatus.RUNNING
        return ingestion_job

    def mark_completed(ingestion_job: IngestionJob) -> IngestionJob:
        ingestion_job.status = IngestionJobStatus.COMPLETED
        ingestion_job.progress = 100
        return ingestion_job

    def mark_failed(
        ingestion_job: IngestionJob,
        *,
        error_message: str,
    ) -> IngestionJob:
        ingestion_job.status = IngestionJobStatus.FAILED
        ingestion_job.error_message = error_message
        return ingestion_job

    ingestion_service.mark_queued.side_effect = mark_queued
    ingestion_service.mark_running.side_effect = mark_running
    ingestion_service.mark_completed.side_effect = mark_completed
    ingestion_service.mark_failed.side_effect = mark_failed

    worker = IngestionWorker(
        session=session,
        consumer=consumer,
        ingestion_service=ingestion_service,
        processor=processor,
        retry_delay_seconds=0,
    )

    return (
        worker,
        session,
        consumer,
        ingestion_service,
        processor,
    )


@pytest.mark.asyncio
async def test_run_once_processes_and_acknowledges_queued_job() -> None:
    worker, session, consumer, ingestion_service, processor = make_worker()
    ingestion_job = make_ingestion_job()
    consumer.read.return_value = make_message(ingestion_job.id)
    ingestion_service.get_job.return_value = ingestion_job

    processed = await worker.run_once()

    assert processed is True
    ingestion_service.mark_running.assert_awaited_once_with(ingestion_job)
    processor.process.assert_awaited_once_with(ingestion_job)
    ingestion_service.mark_completed.assert_awaited_once_with(ingestion_job)
    assert session.commit.await_count == 2
    session.rollback.assert_not_awaited()
    consumer.acknowledge.assert_awaited_once_with("123-0")


@pytest.mark.asyncio
async def test_run_once_promotes_legacy_pending_job_before_processing() -> None:
    worker, _, consumer, ingestion_service, processor = make_worker()
    ingestion_job = make_ingestion_job(
        status=IngestionJobStatus.PENDING,
    )
    consumer.read.return_value = make_message(ingestion_job.id)
    ingestion_service.get_job.return_value = ingestion_job

    processed = await worker.run_once()

    assert processed is True
    ingestion_service.mark_queued.assert_awaited_once_with(ingestion_job)
    ingestion_service.mark_running.assert_awaited_once_with(ingestion_job)
    processor.process.assert_awaited_once_with(ingestion_job)


@pytest.mark.asyncio
async def test_run_once_records_processor_failure_before_acknowledging() -> None:
    worker, session, consumer, ingestion_service, processor = make_worker()
    ingestion_job = make_ingestion_job()
    consumer.read.return_value = make_message(ingestion_job.id)
    ingestion_service.get_job.return_value = ingestion_job
    processor.process.side_effect = RuntimeError("Clone failed")

    processed = await worker.run_once()

    assert processed is True
    ingestion_service.mark_failed.assert_awaited_once_with(
        ingestion_job,
        error_message="Clone failed",
    )
    assert session.rollback.await_count == 1
    assert session.commit.await_count == 2
    consumer.acknowledge.assert_awaited_once_with("123-0")


@pytest.mark.asyncio
async def test_run_once_does_not_acknowledge_database_failure() -> None:
    worker, session, consumer, ingestion_service, processor = make_worker()
    ingestion_job = make_ingestion_job()
    consumer.read.return_value = make_message(ingestion_job.id)
    ingestion_service.get_job.return_value = ingestion_job
    ingestion_service.mark_running.side_effect = RuntimeError("Database unavailable")

    with pytest.raises(
        RuntimeError,
        match="Database unavailable",
    ):
        await worker.run_once()

    session.rollback.assert_awaited_once_with()
    processor.process.assert_not_awaited()
    consumer.acknowledge.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        IngestionJobStatus.COMPLETED,
        IngestionJobStatus.FAILED,
    ],
)
async def test_run_once_acknowledges_terminal_job_without_reprocessing(
    status: IngestionJobStatus,
) -> None:
    worker, session, consumer, ingestion_service, processor = make_worker()
    ingestion_job = make_ingestion_job(status=status)
    consumer.read.return_value = make_message(ingestion_job.id)
    ingestion_service.get_job.return_value = ingestion_job

    processed = await worker.run_once()

    assert processed is True
    processor.process.assert_not_awaited()
    session.commit.assert_not_awaited()
    consumer.acknowledge.assert_awaited_once_with("123-0")


@pytest.mark.asyncio
async def test_run_once_acknowledges_message_for_deleted_job() -> None:
    worker, _, consumer, ingestion_service, processor = make_worker()
    ingestion_job_id = uuid4()
    consumer.read.return_value = make_message(ingestion_job_id)
    ingestion_service.get_job.side_effect = IngestionJobNotFoundError()

    processed = await worker.run_once()

    assert processed is True
    processor.process.assert_not_awaited()
    consumer.acknowledge.assert_awaited_once_with("123-0")


@pytest.mark.asyncio
async def test_run_once_acknowledges_poison_message() -> None:
    worker, _, consumer, ingestion_service, processor = make_worker()
    consumer.read.side_effect = InvalidIngestionMessageError(
        entry_id="bad-0",
        message="Missing job id",
    )

    processed = await worker.run_once()

    assert processed is True
    ingestion_service.get_job.assert_not_awaited()
    processor.process.assert_not_awaited()
    consumer.acknowledge.assert_awaited_once_with("bad-0")


@pytest.mark.asyncio
async def test_run_once_returns_false_when_stream_is_idle() -> None:
    worker, _, consumer, ingestion_service, processor = make_worker()
    consumer.read.return_value = None

    processed = await worker.run_once()

    assert processed is False
    ingestion_service.get_job.assert_not_awaited()
    processor.process.assert_not_awaited()
    consumer.acknowledge.assert_not_awaited()
