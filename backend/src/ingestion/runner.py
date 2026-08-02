import asyncio
import logging
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import IngestionJobNotFoundError, RetryableGitHubAPIError
from src.ingestion.models import IngestionJob, IngestionJobStatus
from src.ingestion.queue import (
    IngestionConsumer,
    IngestionMessage,
    InvalidIngestionMessageError,
)
from src.ingestion.service import IngestionService

logger = logging.getLogger(__name__)

MAX_ERROR_MESSAGE_LENGTH = 2_000


class IngestionJobProcessor(Protocol):
    async def process(self, ingestion_job: IngestionJob) -> None: ...


class IngestionWorker:
    def __init__(
        self,
        *,
        session: AsyncSession,
        consumer: IngestionConsumer,
        ingestion_service: IngestionService,
        processor: IngestionJobProcessor,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        self.session = session
        self.consumer = consumer
        self.ingestion_service = ingestion_service
        self.processor = processor
        self.retry_delay_seconds = retry_delay_seconds

    async def run_forever(self) -> None:
        await self.consumer.ensure_group()
        await self.recover_running_jobs()

        while True:
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Ingestion worker iteration failed")
                await asyncio.sleep(self.retry_delay_seconds)

    async def recover_running_jobs(self) -> int:
        running_jobs = await self.ingestion_service.list_running_jobs()
        await self.session.commit()
        recovered = await self.consumer.recover([job.id for job in running_jobs])
        if recovered:
            logger.warning(
                "Recovered orphaned ingestion jobs",
                extra={"recovered_jobs": recovered},
            )
        return recovered

    async def run_once(self) -> bool:
        try:
            message = await self.consumer.read()
        except InvalidIngestionMessageError as error:
            logger.error(
                "Discarding invalid ingestion message",
                extra={
                    "entry_id": error.entry_id,
                    "reason": str(error),
                },
            )
            await self.consumer.acknowledge(error.entry_id)
            return True

        if message is None:
            return False

        try:
            ingestion_job = await self.ingestion_service.get_job(
                message.ingestion_job_id,
            )
        except IngestionJobNotFoundError:
            logger.warning(
                "Acknowledging ingestion message for missing job",
                extra={
                    "ingestion_job_id": str(message.ingestion_job_id),
                },
            )
            await self.consumer.acknowledge(message.entry_id)
            return True

        if ingestion_job.status in {
            IngestionJobStatus.COMPLETED,
            IngestionJobStatus.FAILED,
        }:
            await self.consumer.acknowledge(message.entry_id)
            return True

        await self._start_job(ingestion_job)

        try:
            await self.processor.process(ingestion_job)
        except RetryableGitHubAPIError as error:
            await self.session.rollback()
            logger.warning(
                "Ingestion provider call will be retried",
                extra={
                    "ingestion_job_id": str(message.ingestion_job_id),
                    "reason": str(error),
                },
            )
            return True
        except Exception as error:
            await self._record_failure(
                message=message,
                error=error,
            )
            return True

        try:
            await self.ingestion_service.mark_completed(ingestion_job)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.consumer.acknowledge(message.entry_id)
        return True

    async def _start_job(self, ingestion_job: IngestionJob) -> None:
        try:
            if ingestion_job.status is IngestionJobStatus.PENDING:
                await self.ingestion_service.mark_queued(ingestion_job)

            if ingestion_job.status is IngestionJobStatus.QUEUED:
                await self.ingestion_service.mark_running(ingestion_job)

            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def _record_failure(
        self,
        *,
        message: IngestionMessage,
        error: Exception,
    ) -> None:
        await self.session.rollback()

        try:
            ingestion_job = await self.ingestion_service.get_job(
                message.ingestion_job_id,
            )

            if ingestion_job.status in {
                IngestionJobStatus.PENDING,
                IngestionJobStatus.QUEUED,
                IngestionJobStatus.RUNNING,
            }:
                error_message = str(error) or type(error).__name__
                await self.ingestion_service.mark_failed(
                    ingestion_job,
                    error_message=error_message[:MAX_ERROR_MESSAGE_LENGTH],
                )
                await self.session.commit()
        except IngestionJobNotFoundError:
            pass
        except Exception:
            await self.session.rollback()
            raise

        logger.error(
            "Ingestion job failed",
            extra={
                "ingestion_job_id": str(message.ingestion_job_id),
            },
            exc_info=error,
        )
        await self.consumer.acknowledge(message.entry_id)
