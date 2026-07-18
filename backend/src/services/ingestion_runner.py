import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.github_client import GitHubClient
from src.models.enums import IngestionJobStatus
from src.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)


class IngestionRunner:
    def __init__(
        self,
        session: AsyncSession,
        *,
        github_client: GitHubClient,
    ) -> None:
        self.ingestion_service = IngestionService(session)
        self.github_client = github_client

    async def run(
        self,
        *,
        job_id: int,
        owner: str,
        name: str,
    ) -> None:
        await self.ingestion_service.update_ingestion_job(
            job_id=job_id,
            status=IngestionJobStatus.RUNNING,
            progress=10,
        )

        try:
            await self._ingest(
                owner=owner,
                name=name,
            )

            await self.ingestion_service.update_ingestion_job(
                job_id=job_id,
                status=IngestionJobStatus.COMPLETED,
                progress=100,
            )
        except Exception as error:
            try:
                await self.ingestion_service.update_ingestion_job(
                    job_id=job_id,
                    status=IngestionJobStatus.FAILED,
                    progress=10,
                    error_message=str(error),
                )
            except Exception:
                logger.exception(
                    "Failed to mark ingestion job %s as failed",
                    job_id,
                )

            raise

    async def _ingest(
        self,
        *,
        owner: str,
        name: str,
    ) -> None:
        await self.github_client.get_repository(
            owner=owner,
            name=name,
        )
