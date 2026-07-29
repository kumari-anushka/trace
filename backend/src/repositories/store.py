from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.models import Repository


class RepositoryStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        github_id: int,
        github_url: str,
        owner: str,
        name: str,
        default_branch: str,
    ) -> Repository:
        repository = Repository(
            github_id=github_id,
            github_url=github_url,
            owner=owner,
            name=name,
            default_branch=default_branch,
        )

        self.session.add(repository)
        await self.session.flush()

        return repository

    async def get_by_id(
        self,
        repository_id: UUID,
    ) -> Repository | None:
        return await self.session.get(
            Repository,
            repository_id,
        )

    async def get_by_github_id(
        self,
        github_id: int,
    ) -> Repository | None:
        statement = select(Repository).where(
            Repository.github_id == github_id,
        )

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def get_by_github_url(
        self,
        github_url: str,
    ) -> Repository | None:
        statement = select(Repository).where(
            Repository.github_url == github_url,
        )

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def list_all(self) -> Sequence[Repository]:
        statement = select(Repository).order_by(
            Repository.created_at.desc(),
        )

        result = await self.session.execute(statement)

        return result.scalars().all()

    async def delete(
        self,
        repository: Repository,
    ) -> None:
        await self.session.delete(repository)
        await self.session.flush()
