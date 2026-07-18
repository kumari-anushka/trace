from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.github_client import GitHubClient
from src.core.exceptions import RepositoryNotFoundError
from src.models.ingestion_job import IngestionJob
from src.models.repository_snapshot import RepositorySnapshot
from src.services.ingestion_service import IngestionService
from src.services.repository_service import RepositoryService


class IngestionCoordinator:
    def __init__(
        self,
        session: AsyncSession,
        *,
        github_client: GitHubClient,
    ) -> None:
        self.repository_service = RepositoryService(session)
        self.ingestion_service = IngestionService(session)
        self.github_client = github_client

    async def create_ingestion(
        self,
        *,
        repository_id: int,
    ) -> tuple[RepositorySnapshot, IngestionJob]:
        repository = await self.repository_service.get_repository(
            repository_id=repository_id,
        )

        if repository is None:
            raise RepositoryNotFoundError

        repository_metadata = await self.github_client.get_repository(
            owner=repository.owner,
            name=repository.name,
        )

        commit_metadata = await self.github_client.get_commit(
            owner=repository.owner,
            name=repository.name,
            ref=repository_metadata.default_branch,
        )

        return await self.ingestion_service.create_ingestion(
            repository=repository,
            commit_sha=commit_metadata.sha,
            default_branch=repository_metadata.default_branch,
        )
