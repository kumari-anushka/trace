from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import IngestionJobNotFoundError, RepositoryNotFoundError
from src.ingestion.models import IngestionJob, IngestionStage
from src.ingestion.store import IngestionJobStore, IngestionStageStore
from src.repositories.models import Repository
from src.repositories.store import RepositoryStore


@dataclass(frozen=True, slots=True)
class RepositoryIngestionStatus:
    repository_id: UUID
    ingestion_job: IngestionJob
    stages: Sequence[IngestionStage]


class RepositoryService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        store: RepositoryStore,
    ) -> None:
        self.session = session
        self.store = store

    async def get_repository(
        self,
        repository_id: UUID,
    ) -> Repository:
        repository = await self.store.get_by_id(repository_id)

        if repository is None:
            raise RepositoryNotFoundError

        return repository

    async def list_repositories(
        self,
    ) -> Sequence[Repository]:
        return await self.store.list_all()

    async def delete_repository(
        self,
        repository_id: UUID,
    ) -> None:
        repository = await self.store.get_by_id(repository_id)

        if repository is None:
            raise RepositoryNotFoundError

        try:
            await self.store.delete(repository)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise


class RepositoryIngestionService:
    def __init__(
        self,
        *,
        repository_store: RepositoryStore,
        ingestion_job_store: IngestionJobStore,
        ingestion_stage_store: IngestionStageStore,
    ) -> None:
        self.repository_store = repository_store
        self.ingestion_job_store = ingestion_job_store
        self.ingestion_stage_store = ingestion_stage_store

    async def get_status(
        self,
        repository_id: UUID,
    ) -> RepositoryIngestionStatus:
        repository = await self.repository_store.get_by_id(
            repository_id,
        )

        if repository is None:
            raise RepositoryNotFoundError

        ingestion_job = await self.ingestion_job_store.get_latest_by_repository(
            repository_id,
        )

        if ingestion_job is None:
            raise IngestionJobNotFoundError

        stages = await self.ingestion_stage_store.list_by_ingestion_job(
            ingestion_job.id,
        )

        return RepositoryIngestionStatus(
            repository_id=repository.id,
            ingestion_job=ingestion_job,
            stages=stages,
        )
