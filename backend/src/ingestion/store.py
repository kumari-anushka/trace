from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ingestion.models import IngestionJob, IngestionJobStatus


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

    async def flush(
        self,
        ingestion_job: IngestionJob,
    ) -> IngestionJob:
        await self.session.flush()

        return ingestion_job
