from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.models import (
    IngestionJob,
    IngestionStage,
    IngestionStageStatus,
)
from src.ingestion.runner import MAX_ERROR_MESSAGE_LENGTH
from src.ingestion.service import IngestionService, IngestionStageService
from src.repository_versions.service import RepositoryVersionService

FOUNDATION_STAGE_NAME = "prepare_repository_snapshot"


class FoundationIngestionProcessor:
    def __init__(
        self,
        *,
        session: AsyncSession,
        ingestion_service: IngestionService,
        stage_service: IngestionStageService,
        repository_version_service: RepositoryVersionService,
    ) -> None:
        self.session = session
        self.ingestion_service = ingestion_service
        self.stage_service = stage_service
        self.repository_version_service = repository_version_service

    async def process(self, ingestion_job: IngestionJob) -> None:
        ingestion_stage = await self._get_or_create_stage(ingestion_job)

        if ingestion_stage.status is IngestionStageStatus.COMPLETED:
            await self.ingestion_service.update_progress(
                ingestion_job,
                progress=99,
            )
            await self.session.commit()
            return

        if ingestion_stage.status in {
            IngestionStageStatus.FAILED,
            IngestionStageStatus.SKIPPED,
        }:
            raise RuntimeError(
                f"Foundation stage cannot resume from {ingestion_stage.status.value}",
            )

        try:
            if ingestion_stage.status is IngestionStageStatus.PENDING:
                await self.stage_service.mark_running(ingestion_stage)

            await self.ingestion_service.update_progress(
                ingestion_job,
                progress=10,
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        try:
            await self.repository_version_service.get_repository_version(
                ingestion_job.repository_version_id,
            )
            await self.stage_service.mark_completed(ingestion_stage)
            await self.ingestion_service.update_progress(
                ingestion_job,
                progress=99,
            )
            await self.session.commit()
        except Exception as error:
            await self._record_stage_failure(
                ingestion_stage=ingestion_stage,
                error=error,
            )
            raise

    async def _get_or_create_stage(
        self,
        ingestion_job: IngestionJob,
    ) -> IngestionStage:
        stages = await self.stage_service.list_stages(
            ingestion_job.id,
        )

        for ingestion_stage in stages:
            if ingestion_stage.name == FOUNDATION_STAGE_NAME:
                return ingestion_stage

        return await self.stage_service.create_stage(
            ingestion_job_id=ingestion_job.id,
            name=FOUNDATION_STAGE_NAME,
            position=0,
        )

    async def _record_stage_failure(
        self,
        *,
        ingestion_stage: IngestionStage,
        error: Exception,
    ) -> None:
        ingestion_stage_id = ingestion_stage.id
        await self.session.rollback()

        try:
            persisted_stage = await self.stage_service.get_stage(
                ingestion_stage_id,
            )

            if persisted_stage.status in {
                IngestionStageStatus.PENDING,
                IngestionStageStatus.RUNNING,
            }:
                error_message = str(error) or type(error).__name__
                await self.stage_service.mark_failed(
                    persisted_stage,
                    error_message=error_message[:MAX_ERROR_MESSAGE_LENGTH],
                )
                await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
