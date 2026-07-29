from collections.abc import Sequence
from uuid import UUID

from src.core.exceptions import RepositoryVersionNotFoundError
from src.repository_versions.models import RepositoryVersion
from src.repository_versions.store import RepositoryVersionStore


class RepositoryVersionService:
    def __init__(
        self,
        *,
        store: RepositoryVersionStore,
    ) -> None:
        self.store = store

    async def get_repository_version(
        self,
        repository_version_id: UUID,
    ) -> RepositoryVersion:
        repository_version = await self.store.get_by_id(
            repository_version_id,
        )

        if repository_version is None:
            raise RepositoryVersionNotFoundError

        return repository_version

    async def list_repository_versions(
        self,
        repository_id: UUID,
    ) -> Sequence[RepositoryVersion]:
        return await self.store.list_by_repository(
            repository_id,
        )
