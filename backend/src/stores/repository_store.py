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
    ) -> Repository:
        repository = Repository(
            github_url=github_url,
            owner=owner,
            name=name,
        )

        self.session.add(repository)
        await self.session.commit()
        await self.session.refresh(repository)

        return repository

    async def list_all(self) -> list[Repository]:
        statement = select(Repository).order_by(Repository.created_at.desc())
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_by_id(self, repository_id: int) -> Repository | None:
        return await self.session.get(Repository, repository_id)

    async def delete(self, repository: Repository) -> None:
        await self.session.delete(repository)
        await self.session.commit()
