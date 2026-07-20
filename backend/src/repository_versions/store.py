from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.repository_versions.models import RepositoryVersion


class RepositoryVersionStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        repository_id: UUID,
        commit_sha: str,
        branch: str,
    ) -> RepositoryVersion:
        repository_version = RepositoryVersion(
            repository_id=repository_id,
            commit_sha=commit_sha,
            branch=branch,
        )

        self.session.add(repository_version)
        await self.session.flush()

        return repository_version

    async def get_by_id(
        self,
        repository_version_id: UUID,
    ) -> RepositoryVersion | None:
        return await self.session.get(
            RepositoryVersion,
            repository_version_id,
        )

    async def get_by_repository_and_commit(
        self,
        *,
        repository_id: UUID,
        commit_sha: str,
    ) -> RepositoryVersion | None:
        statement = select(RepositoryVersion).where(
            RepositoryVersion.repository_id == repository_id,
            RepositoryVersion.commit_sha == commit_sha,
        )

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def list_by_repository(
        self,
        repository_id: UUID,
    ) -> Sequence[RepositoryVersion]:
        statement = (
            select(RepositoryVersion)
            .where(
                RepositoryVersion.repository_id == repository_id,
            )
            .order_by(
                RepositoryVersion.created_at.desc(),
            )
        )

        result = await self.session.execute(statement)

        return result.scalars().all()
