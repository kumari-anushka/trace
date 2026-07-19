from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.github_client import GitHubClient
from src.models.repository import Repository
from src.services.ingestion_service import IngestionService
from src.services.repository_service import RepositoryService


class RepositoryCreationService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        github_client: GitHubClient,
    ) -> None:
        self.github_client = github_client
        self.repository_service = RepositoryService(session)
        self.ingestion_service = IngestionService(session)

    async def create_repository(
        self,
        *,
        github_url: str,
    ) -> Repository:
        normalized_url, owner, name = self.repository_service.parse_github_url(
            github_url,
        )

        github_repository = await self.github_client.get_repository(
            owner=owner,
            name=name,
        )

        repository = await self.repository_service.create_repository(
            github_url=normalized_url,
            owner=owner,
            name=name,
        )

        commit = await self.github_client.get_commit(
            owner=owner,
            name=name,
            ref=github_repository.default_branch,
        )

        await self.ingestion_service.create_ingestion(
            repository=repository,
            commit_sha=commit.sha,
            default_branch=github_repository.default_branch,
        )

        return repository
