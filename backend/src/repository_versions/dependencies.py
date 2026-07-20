from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dependencies import get_session
from src.repository_versions.service import RepositoryVersionService
from src.repository_versions.store import RepositoryVersionStore

SessionDependency = Annotated[
    AsyncSession,
    Depends(get_session),
]


def get_repository_version_service(
    session: SessionDependency,
) -> RepositoryVersionService:
    repository_version_store = RepositoryVersionStore(
        session=session,
    )

    return RepositoryVersionService(
        store=repository_version_store,
    )
