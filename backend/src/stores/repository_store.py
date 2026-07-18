from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.repository import Repository


class RepositoryStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_github_url(
        self,
        github_url: str,
    ) -> Repository | None:
        statement = select(Repository).where(
            Repository.github_url == github_url,
        )

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        github_url: str,
        owner: str,
        name: str,
        default_branch: str,
    ) -> Repository:
        repository = Repository(
            github_url=github_url,
            owner=owner,
            name=name,
            default_branch=default_branch,
        )

        self.session.add(repository)
        await self.session.commit()
        await self.session.refresh(repository)

        return repository
