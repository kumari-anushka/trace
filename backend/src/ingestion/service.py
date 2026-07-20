from datetime import UTC, datetime
from uuid import UUID

from src.core.exceptions import (
    IngestionJobNotFoundError,
    InvalidIngestionJobTransitionError,
    InvalidIngestionProgressError,
)
from src.ingestion.models import IngestionJob, IngestionJobStatus
from src.ingestion.store import IngestionJobStore

ALLOWED_STATUS_TRANSITIONS: dict[
    IngestionJobStatus,
    set[IngestionJobStatus],
] = {
    IngestionJobStatus.PENDING: {
        IngestionJobStatus.QUEUED,
        IngestionJobStatus.FAILED,
    },
    IngestionJobStatus.QUEUED: {
        IngestionJobStatus.RUNNING,
        IngestionJobStatus.FAILED,
    },
    IngestionJobStatus.RUNNING: {
        IngestionJobStatus.COMPLETED,
        IngestionJobStatus.FAILED,
    },
    IngestionJobStatus.COMPLETED: set(),
    IngestionJobStatus.FAILED: set(),
}


class IngestionService:
    def __init__(
        self,
        *,
        store: IngestionJobStore,
    ) -> None:
        self.store = store

    async def create_job(
        self,
        *,
        repository_version_id: UUID,
    ) -> IngestionJob:
        return await self.store.create(
            repository_version_id=repository_version_id,
        )

    async def get_job(
        self,
        ingestion_job_id: UUID,
    ) -> IngestionJob:
        ingestion_job = await self.store.get_by_id(
            ingestion_job_id,
        )

        if ingestion_job is None:
            raise IngestionJobNotFoundError

        return ingestion_job

    async def mark_queued(
        self,
        ingestion_job: IngestionJob,
    ) -> IngestionJob:
        self._transition_to(
            ingestion_job,
            IngestionJobStatus.QUEUED,
        )

        return await self.store.flush(ingestion_job)

    async def mark_running(
        self,
        ingestion_job: IngestionJob,
    ) -> IngestionJob:
        self._transition_to(
            ingestion_job,
            IngestionJobStatus.RUNNING,
        )

        ingestion_job.started_at = datetime.now(UTC)
        ingestion_job.error_message = None

        return await self.store.flush(ingestion_job)

    async def update_progress(
        self,
        ingestion_job: IngestionJob,
        *,
        progress: int,
    ) -> IngestionJob:
        if ingestion_job.status is not IngestionJobStatus.RUNNING:
            raise InvalidIngestionJobTransitionError(
                "Progress can only be updated for a running ingestion job",
            )

        if progress < 0 or progress >= 100:
            raise InvalidIngestionProgressError(
                "Running ingestion progress must be between 0 and 99",
            )

        ingestion_job.progress = progress

        return await self.store.flush(ingestion_job)

    async def mark_completed(
        self,
        ingestion_job: IngestionJob,
    ) -> IngestionJob:
        self._transition_to(
            ingestion_job,
            IngestionJobStatus.COMPLETED,
        )

        ingestion_job.progress = 100
        ingestion_job.error_message = None
        ingestion_job.completed_at = datetime.now(UTC)

        return await self.store.flush(ingestion_job)

    async def mark_failed(
        self,
        ingestion_job: IngestionJob,
        *,
        error_message: str,
    ) -> IngestionJob:
        self._transition_to(
            ingestion_job,
            IngestionJobStatus.FAILED,
        )

        ingestion_job.error_message = error_message
        ingestion_job.completed_at = datetime.now(UTC)

        return await self.store.flush(ingestion_job)

    @staticmethod
    def _transition_to(
        ingestion_job: IngestionJob,
        target_status: IngestionJobStatus,
    ) -> None:
        allowed_statuses = ALLOWED_STATUS_TRANSITIONS[ingestion_job.status]

        if target_status not in allowed_statuses:
            raise InvalidIngestionJobTransitionError(
                (
                    "Cannot transition ingestion job "
                    f"from {ingestion_job.status.value} "
                    f"to {target_status.value}"
                ),
            )

        ingestion_job.status = target_status
