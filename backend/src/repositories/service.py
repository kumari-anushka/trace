from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import RepositoryNotFoundError
from src.repositories.models import Repository
from src.repositories.store import RepositoryStore


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
