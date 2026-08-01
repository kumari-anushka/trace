from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from src.core.exceptions import (
    IngestionJobNotFoundError,
    IngestionStageNotFoundError,
    InvalidIngestionJobTransitionError,
    InvalidIngestionProgressError,
    InvalidIngestionStageProgressError,
    InvalidIngestionStageTransitionError,
)
from src.ingestion.models import (
    IngestionJob,
    IngestionJobStatus,
    IngestionStage,
    IngestionStageStatus,
)
from src.ingestion.store import IngestionJobStore, IngestionStageStore

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

ALLOWED_STAGE_STATUS_TRANSITIONS: dict[
    IngestionStageStatus,
    set[IngestionStageStatus],
] = {
    IngestionStageStatus.PENDING: {
        IngestionStageStatus.RUNNING,
        IngestionStageStatus.FAILED,
        IngestionStageStatus.SKIPPED,
    },
    IngestionStageStatus.RUNNING: {
        IngestionStageStatus.COMPLETED,
        IngestionStageStatus.FAILED,
    },
    IngestionStageStatus.COMPLETED: set(),
    IngestionStageStatus.FAILED: set(),
    IngestionStageStatus.SKIPPED: set(),
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


class IngestionStageService:
    def __init__(
        self,
        *,
        store: IngestionStageStore,
    ) -> None:
        self.store = store

    async def create_stage(
        self,
        *,
        ingestion_job_id: UUID,
        name: str,
        position: int,
    ) -> IngestionStage:
        return await self.store.create(
            ingestion_job_id=ingestion_job_id,
            name=name,
            position=position,
        )

    async def get_stage(
        self,
        ingestion_stage_id: UUID,
    ) -> IngestionStage:
        ingestion_stage = await self.store.get_by_id(
            ingestion_stage_id,
        )

        if ingestion_stage is None:
            raise IngestionStageNotFoundError

        return ingestion_stage

    async def list_stages(
        self,
        ingestion_job_id: UUID,
    ) -> Sequence[IngestionStage]:
        return await self.store.list_by_ingestion_job(
            ingestion_job_id,
        )

    async def mark_running(
        self,
        ingestion_stage: IngestionStage,
    ) -> IngestionStage:
        self._transition_to(
            ingestion_stage,
            IngestionStageStatus.RUNNING,
        )
        ingestion_stage.started_at = datetime.now(UTC)
        ingestion_stage.error_message = None

        return await self.store.flush(ingestion_stage)

    async def update_progress(
        self,
        ingestion_stage: IngestionStage,
        *,
        progress: int,
    ) -> IngestionStage:
        if ingestion_stage.status is not IngestionStageStatus.RUNNING:
            raise InvalidIngestionStageTransitionError(
                "Progress can only be updated for a running ingestion stage",
            )

        if progress < 0 or progress >= 100:
            raise InvalidIngestionStageProgressError(
                "Running ingestion stage progress must be between 0 and 99",
            )

        ingestion_stage.progress = progress

        return await self.store.flush(ingestion_stage)

    async def mark_completed(
        self,
        ingestion_stage: IngestionStage,
    ) -> IngestionStage:
        self._transition_to(
            ingestion_stage,
            IngestionStageStatus.COMPLETED,
        )
        ingestion_stage.progress = 100
        ingestion_stage.error_message = None
        ingestion_stage.completed_at = datetime.now(UTC)

        return await self.store.flush(ingestion_stage)

    async def mark_failed(
        self,
        ingestion_stage: IngestionStage,
        *,
        error_message: str,
    ) -> IngestionStage:
        self._transition_to(
            ingestion_stage,
            IngestionStageStatus.FAILED,
        )
        ingestion_stage.error_message = error_message
        ingestion_stage.completed_at = datetime.now(UTC)

        return await self.store.flush(ingestion_stage)

    async def mark_skipped(
        self,
        ingestion_stage: IngestionStage,
    ) -> IngestionStage:
        self._transition_to(
            ingestion_stage,
            IngestionStageStatus.SKIPPED,
        )
        ingestion_stage.completed_at = datetime.now(UTC)

        return await self.store.flush(ingestion_stage)

    @staticmethod
    def _transition_to(
        ingestion_stage: IngestionStage,
        target_status: IngestionStageStatus,
    ) -> None:
        allowed_statuses = ALLOWED_STAGE_STATUS_TRANSITIONS[ingestion_stage.status]

        if target_status not in allowed_statuses:
            raise InvalidIngestionStageTransitionError(
                (
                    "Cannot transition ingestion stage "
                    f"from {ingestion_stage.status.value} "
                    f"to {target_status.value}"
                ),
            )

        ingestion_stage.status = target_status
