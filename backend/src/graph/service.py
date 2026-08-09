from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from src.core.exceptions import RepositoryNotFoundError, RepositoryVersionNotFoundError
from src.graph.models import EntityType, GraphEvidence, KnowledgeKind, RelationshipType
from src.graph.repository import GraphRepository, GraphSnapshot
from src.repositories.store import RepositoryStore
from src.repository_versions.store import RepositoryVersionStore


class GraphService:
    def __init__(
        self,
        *,
        graph_repository: GraphRepository,
        repository_store: RepositoryStore,
        repository_version_store: RepositoryVersionStore,
    ) -> None:
        self.graph_repository = graph_repository
        self.repository_store = repository_store
        self.repository_version_store = repository_version_store

    async def get_graph(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        limit: int,
        edge_limit: int,
        metric_limit: int,
        entity_types: Sequence[EntityType] = (),
        relationship_types: Sequence[RelationshipType] = (),
        knowledge_kinds: Sequence[KnowledgeKind] = (),
        metric_names: Sequence[str] = (),
        include_metrics: bool = True,
    ) -> GraphSnapshot:
        await self._validate_scope(repository_id, repository_version_id)
        return await self.graph_repository.subgraph(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            limit=limit,
            edge_limit=edge_limit,
            metric_limit=metric_limit,
            entity_types=entity_types,
            relationship_types=relationship_types,
            knowledge_kinds=knowledge_kinds,
            metric_names=metric_names,
            include_metrics=include_metrics,
        )

    async def get_neighbors(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        node_id: UUID,
        depth: int,
        limit: int,
        edge_limit: int,
        metric_limit: int,
        entity_types: Sequence[EntityType] = (),
        relationship_types: Sequence[RelationshipType] = (),
        knowledge_kinds: Sequence[KnowledgeKind] = (),
        metric_names: Sequence[str] = (),
        include_metrics: bool = True,
    ) -> GraphSnapshot:
        await self._validate_scope(repository_id, repository_version_id)
        return await self.graph_repository.neighbors(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            node_id=node_id,
            depth=depth,
            limit=limit,
            edge_limit=edge_limit,
            metric_limit=metric_limit,
            entity_types=entity_types,
            relationship_types=relationship_types,
            knowledge_kinds=knowledge_kinds,
            metric_names=metric_names,
            include_metrics=include_metrics,
        )

    async def get_evidence(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        target_node_id: UUID | None,
        target_edge_id: UUID | None,
        limit: int,
    ) -> tuple[Sequence[GraphEvidence], bool]:
        await self._validate_scope(repository_id, repository_version_id)
        return await self.graph_repository.list_evidence(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            target_node_id=target_node_id,
            target_edge_id=target_edge_id,
            limit=limit,
        )

    async def _validate_scope(self, repository_id: UUID, repository_version_id: UUID) -> None:
        repository = await self.repository_store.get_by_id(repository_id)
        if repository is None:
            raise RepositoryNotFoundError
        repository_version = await self.repository_version_store.get_by_id(repository_version_id)
        if repository_version is None or repository_version.repository_id != repository.id:
            raise RepositoryVersionNotFoundError
