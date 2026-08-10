from __future__ import annotations

from uuid import UUID

from src.ask.models import QueryResult
from src.ask.workflow import AskWorkflow
from src.core.exceptions import RepositoryNotFoundError, RepositoryVersionNotFoundError
from src.repositories.store import RepositoryStore
from src.repository_versions.store import RepositoryVersionStore


class RepositoryQueryService:
    def __init__(
        self,
        *,
        repository_store: RepositoryStore,
        repository_version_store: RepositoryVersionStore,
        workflow: AskWorkflow,
    ) -> None:
        self.repository_store = repository_store
        self.repository_version_store = repository_version_store
        self.workflow = workflow

    async def query(self, *, repository_id: UUID, question: str) -> QueryResult:
        repository = await self.repository_store.get_by_id(repository_id)
        if repository is None:
            raise RepositoryNotFoundError
        versions = await self.repository_version_store.list_by_repository(repository_id)
        if not versions:
            raise RepositoryVersionNotFoundError
        return await self.workflow.run(
            repository_id=repository_id,
            repository_version_id=versions[0].id,
            question=question.strip(),
        )
