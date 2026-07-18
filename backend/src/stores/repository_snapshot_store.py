from sqlalchemy.ext.asyncio import AsyncSession

from src.models.repository_snapshot import RepositorySnapshot


class RepositorySnapshotStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(
        self,
        snapshot_id: int,
    ) -> RepositorySnapshot | None:
        return await self.session.get(
            RepositorySnapshot,
            snapshot_id,
        )
