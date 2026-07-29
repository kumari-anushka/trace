from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    IngestionDispatchError,
    RepositoryAlreadyExistsError,
)
from src.github.client import GitHubClient
from src.github.reference import GitHubRepositoryReference
from src.ingestion.models import IngestionJob
from src.ingestion.queue import IngestionQueue
from src.ingestion.service import IngestionService
from src.repositories.models import Repository
from src.repositories.store import RepositoryStore
from src.repository_versions.models import RepositoryVersion
from src.repository_versions.store import RepositoryVersionStore


class RepositoryImportResult:
    def __init__(
        self,
        *,
        repository: Repository,
        repository_version: RepositoryVersion,
        ingestion_job: IngestionJob,
    ) -> None:
        self.repository = repository
        self.repository_version = repository_version
        self.ingestion_job = ingestion_job


class RepositoryImportService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        github_client: GitHubClient,
        repository_store: RepositoryStore,
        repository_version_store: RepositoryVersionStore,
        ingestion_service: IngestionService,
        ingestion_queue: IngestionQueue,
    ) -> None:
        self.session = session
        self.github_client = github_client
        self.repository_store = repository_store
        self.repository_version_store = repository_version_store
        self.ingestion_service = ingestion_service
        self.ingestion_queue = ingestion_queue

    async def import_repository(
        self,
        *,
        github_url: str,
    ) -> RepositoryImportResult:
        reference = GitHubRepositoryReference.from_url(github_url)

        github_repository = await self.github_client.get_repository(
            owner=reference.owner,
            name=reference.name,
        )

        existing_repository = await self.repository_store.get_by_github_id(
            github_repository.github_id,
        )

        if existing_repository is not None:
            raise RepositoryAlreadyExistsError

        github_commit = await self.github_client.get_branch_head(
            owner=reference.owner,
            name=reference.name,
            branch=github_repository.default_branch,
        )

        try:
            repository = await self.repository_store.create(
                github_id=github_repository.github_id,
                github_url=github_repository.html_url,
                owner=github_repository.owner.login,
                name=github_repository.name,
                default_branch=github_repository.default_branch,
            )

            repository_version = await self.repository_version_store.create(
                repository_id=repository.id,
                commit_sha=github_commit.sha,
                branch=github_repository.default_branch,
            )

            ingestion_job = await self.ingestion_service.create_job(
                repository_version_id=repository_version.id,
            )

            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise RepositoryAlreadyExistsError from error
        except Exception:
            await self.session.rollback()
            raise

        try:
            await self.ingestion_queue.enqueue(
                ingestion_job_id=ingestion_job.id,
            )
            await self.ingestion_service.mark_queued(ingestion_job)
            await self.session.commit()
        except Exception as error:
            await self.session.rollback()
            raise IngestionDispatchError from error

        return RepositoryImportResult(
            repository=repository,
            repository_version=repository_version,
            ingestion_job=ingestion_job,
        )
