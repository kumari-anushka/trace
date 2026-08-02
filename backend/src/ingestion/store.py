from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.models import (
    ACTIVE_INGESTION_JOB_STATUSES,
    IngestionJob,
    IngestionJobStatus,
    IngestionStage,
    IngestionStageStatus,
)
from src.repository_versions.models import RepositoryVersion


class IngestionJobStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        repository_version_id: UUID,
    ) -> IngestionJob:
        ingestion_job = IngestionJob(
            repository_version_id=repository_version_id,
            status=IngestionJobStatus.PENDING,
            progress=0,
        )

        self.session.add(ingestion_job)
        await self.session.flush()

        return ingestion_job

    async def get_by_id(
        self,
        ingestion_job_id: UUID,
    ) -> IngestionJob | None:
        return await self.session.get(
            IngestionJob,
            ingestion_job_id,
        )

    async def get_active_by_repository_version(
        self,
        repository_version_id: UUID,
    ) -> IngestionJob | None:
        statement = (
            select(IngestionJob)
            .where(
                IngestionJob.repository_version_id == repository_version_id,
                IngestionJob.status.in_(ACTIVE_INGESTION_JOB_STATUSES),
            )
            .order_by(
                IngestionJob.created_at.desc(),
            )
            .limit(1)
        )

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_repository_version(
        self,
        repository_version_id: UUID,
    ) -> Sequence[IngestionJob]:
        statement = (
            select(IngestionJob)
            .where(
                IngestionJob.repository_version_id == repository_version_id,
            )
            .order_by(
                IngestionJob.created_at.desc(),
            )
        )

        result = await self.session.execute(statement)

        return result.scalars().all()

    async def list_running(self) -> Sequence[IngestionJob]:
        result = await self.session.execute(
            select(IngestionJob).where(IngestionJob.status == IngestionJobStatus.RUNNING)
        )
        return result.scalars().all()

    async def get_latest_by_repository(
        self,
        repository_id: UUID,
    ) -> IngestionJob | None:
        statement = (
            select(IngestionJob)
            .join(
                RepositoryVersion,
                IngestionJob.repository_version_id == RepositoryVersion.id,
            )
            .where(
                RepositoryVersion.repository_id == repository_id,
            )
            .order_by(
                IngestionJob.created_at.desc(),
                IngestionJob.id.desc(),
            )
            .limit(1)
        )

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def flush(
        self,
        ingestion_job: IngestionJob,
    ) -> IngestionJob:
        await self.session.flush()

        return ingestion_job


class IngestionStageStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        ingestion_job_id: UUID,
        name: str,
        position: int,
    ) -> IngestionStage:
        ingestion_stage = IngestionStage(
            ingestion_job_id=ingestion_job_id,
            name=name,
            position=position,
            status=IngestionStageStatus.PENDING,
            progress=0,
        )

        self.session.add(ingestion_stage)
        await self.session.flush()

        return ingestion_stage

    async def get_by_id(
        self,
        ingestion_stage_id: UUID,
    ) -> IngestionStage | None:
        return await self.session.get(
            IngestionStage,
            ingestion_stage_id,
        )

    async def list_by_ingestion_job(
        self,
        ingestion_job_id: UUID,
    ) -> Sequence[IngestionStage]:
        statement = (
            select(IngestionStage)
            .where(
                IngestionStage.ingestion_job_id == ingestion_job_id,
            )
            .order_by(
                IngestionStage.position.asc(),
            )
        )

        result = await self.session.execute(statement)

        return result.scalars().all()

    async def flush(
        self,
        ingestion_stage: IngestionStage,
    ) -> IngestionStage:
        await self.session.flush()

        return ingestion_stage
