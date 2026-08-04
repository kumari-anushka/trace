from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dependencies import get_session
from src.graph.repository import PostgresGraphRepository
from src.graph.service import GraphService
from src.repositories.store import RepositoryStore
from src.repository_versions.store import RepositoryVersionStore

SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def get_graph_service(session: SessionDependency) -> GraphService:
    return GraphService(
        graph_repository=PostgresGraphRepository(session=session),
        repository_store=RepositoryStore(session=session),
        repository_version_store=RepositoryVersionStore(session=session),
    )
