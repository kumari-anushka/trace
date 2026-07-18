from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ingestion_job import IngestionJob


class IngestionJobStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self,
        job_id: int,
    ) -> IngestionJob | None:
        return await self.session.get(IngestionJob, job_id)
