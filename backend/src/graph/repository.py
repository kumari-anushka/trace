from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from math import isfinite
from typing import Protocol
from uuid import UUID

from sqlalchemy import ColumnElement, delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import GraphNodeNotFoundError
from src.core.ontology import ONTOLOGY_VERSION
from src.graph.models import (
    EntityType,
    EvidenceType,
    GraphEdge,
    GraphEvidence,
    GraphMetric,
    GraphNode,
    KnowledgeKind,
    RelationshipType,
)

MAX_GRAPH_RESULT_NODES = 500
MAX_GRAPH_RESULT_EDGES = 2_000
MAX_GRAPH_RESULT_METRICS = 5_000
MAX_ANALYSIS_NODES = 25_000
MAX_ANALYSIS_EDGES = 100_000
MAX_METRIC_BATCH_SIZE = 1_000


@dataclass(frozen=True, slots=True)
class GraphNodeInput:
    repository_id: UUID
    repository_version_id: UUID | None
    entity_type: EntityType
    canonical_key: str
    name: str
    provenance: dict[str, object]
    knowledge_kind: KnowledgeKind = KnowledgeKind.DETERMINISTIC
    confidence: float = 1.0
    description: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    ontology_version: str = ONTOLOGY_VERSION


@dataclass(frozen=True, slots=True)
class GraphEdgeInput:
    repository_id: UUID
    repository_version_id: UUID | None
    source_node_id: UUID
    target_node_id: UUID
    relationship_type: RelationshipType
    provenance: dict[str, object]
    knowledge_kind: KnowledgeKind = KnowledgeKind.DETERMINISTIC
    confidence: float = 1.0
    metadata: dict[str, object] = field(default_factory=dict)
    ontology_version: str = ONTOLOGY_VERSION


@dataclass(frozen=True, slots=True)
class GraphEvidenceInput:
    repository_id: UUID
    repository_version_id: UUID | None
    canonical_key: str
    source_node_id: UUID
    evidence_type: EvidenceType
    provenance: dict[str, object]
    target_node_id: UUID | None = None
    target_edge_id: UUID | None = None
    relationship: RelationshipType | None = None
    excerpt: str | None = None
    source_url: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    confidence: float = 1.0
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphMetricInput:
    repository_id: UUID
    repository_version_id: UUID
    metric_name: str
    scope_key: str
    value: float
    algorithm_version: str
    node_id: UUID | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphSnapshot:
    nodes: Sequence[GraphNode]
    edges: Sequence[GraphEdge]
    metrics: Sequence[GraphMetric] = ()
    nodes_truncated: bool = False
    edges_truncated: bool = False
    metrics_truncated: bool = False


class GraphInvariantError(ValueError):
    """Raised before invalid ontology data reaches persistence."""


class GraphAnalysisLimitError(RuntimeError):
    """Raised when a repository graph exceeds safe in-process analysis bounds."""


class GraphRepository(Protocol):
    async def upsert_node(self, node: GraphNodeInput) -> GraphNode: ...

    async def upsert_edge(self, edge: GraphEdgeInput) -> GraphEdge: ...

    async def upsert_evidence(self, evidence: GraphEvidenceInput) -> GraphEvidence: ...

    async def upsert_metric(self, metric: GraphMetricInput) -> GraphMetric: ...

    async def neighbors(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        node_id: UUID,
        depth: int = 1,
        limit: int = 100,
        edge_limit: int = 1_000,
        metric_limit: int = 2_000,
        entity_types: Sequence[EntityType] = (),
        relationship_types: Sequence[RelationshipType] = (),
        knowledge_kinds: Sequence[KnowledgeKind] = (),
        metric_names: Sequence[str] = (),
        include_metrics: bool = True,
    ) -> GraphSnapshot: ...

    async def subgraph(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        limit: int = MAX_GRAPH_RESULT_NODES,
        edge_limit: int = 1_000,
        metric_limit: int = 2_000,
        entity_types: Sequence[EntityType] = (),
        relationship_types: Sequence[RelationshipType] = (),
        knowledge_kinds: Sequence[KnowledgeKind] = (),
        metric_names: Sequence[str] = (),
        include_metrics: bool = True,
    ) -> GraphSnapshot: ...


class PostgresGraphRepository:
    """PostgreSQL implementation with deterministic conflict identities."""

    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def upsert_node(self, node: GraphNodeInput) -> GraphNode:
        _validate_confidence(node.confidence)
        _validate_required(node.entity_type.value, "entity_type")
        _validate_required(node.canonical_key, "canonical_key")
        _validate_required(node.name, "name")
        _validate_provenance(node.provenance)

        values = {
            "repository_id": node.repository_id,
            "repository_version_id": node.repository_version_id,
            "entity_type": node.entity_type.value,
            "canonical_key": node.canonical_key,
            "name": node.name,
            "description": node.description,
            "knowledge_kind": node.knowledge_kind.value,
            "confidence": node.confidence,
            "provenance": node.provenance,
            "details": node.metadata,
            "ontology_version": node.ontology_version,
        }
        insert_statement = insert(GraphNode).values(**values)
        statement = insert_statement.on_conflict_do_update(
            constraint="uq_graph_nodes_repository_canonical_key",
            set_={
                "repository_version_id": insert_statement.excluded.repository_version_id,
                "entity_type": insert_statement.excluded.entity_type,
                "name": insert_statement.excluded.name,
                "description": insert_statement.excluded.description,
                "knowledge_kind": insert_statement.excluded.knowledge_kind,
                "confidence": insert_statement.excluded.confidence,
                "provenance": insert_statement.excluded.provenance,
                "metadata": insert_statement.excluded.metadata,
                "ontology_version": insert_statement.excluded.ontology_version,
                "updated_at": insert_statement.excluded.updated_at,
            },
        ).returning(GraphNode)
        result = await self.session.execute(statement)
        return result.scalar_one()

    async def upsert_edge(self, edge: GraphEdgeInput) -> GraphEdge:
        _validate_confidence(edge.confidence)
        _validate_required(edge.relationship_type.value, "relationship_type")
        _validate_provenance(edge.provenance)
        if edge.source_node_id == edge.target_node_id:
            raise GraphInvariantError("Graph edges cannot be self-loops")
        await self._validate_node_repositories(
            edge.repository_id,
            (edge.source_node_id, edge.target_node_id),
        )

        values = {
            "repository_id": edge.repository_id,
            "repository_version_id": edge.repository_version_id,
            "source_node_id": edge.source_node_id,
            "target_node_id": edge.target_node_id,
            "relationship_type": edge.relationship_type.value,
            "knowledge_kind": edge.knowledge_kind.value,
            "confidence": edge.confidence,
            "provenance": edge.provenance,
            "details": edge.metadata,
            "ontology_version": edge.ontology_version,
        }
        insert_statement = insert(GraphEdge).values(**values)
        statement = insert_statement.on_conflict_do_update(
            constraint="uq_graph_edges_relation_identity",
            set_={
                "repository_version_id": insert_statement.excluded.repository_version_id,
                "knowledge_kind": insert_statement.excluded.knowledge_kind,
                "confidence": insert_statement.excluded.confidence,
                "provenance": insert_statement.excluded.provenance,
                "metadata": insert_statement.excluded.metadata,
                "ontology_version": insert_statement.excluded.ontology_version,
                "updated_at": insert_statement.excluded.updated_at,
            },
        ).returning(GraphEdge)
        result = await self.session.execute(statement)
        return result.scalar_one()

    async def upsert_evidence(self, evidence: GraphEvidenceInput) -> GraphEvidence:
        _validate_confidence(evidence.confidence)
        _validate_required(evidence.canonical_key, "canonical_key")
        _validate_provenance(evidence.provenance)
        if (evidence.target_node_id is None) == (evidence.target_edge_id is None):
            raise GraphInvariantError("Evidence must target exactly one node or edge")
        if (
            evidence.start_line is not None
            and evidence.end_line is not None
            and evidence.end_line < evidence.start_line
        ):
            raise GraphInvariantError("Evidence end_line cannot precede start_line")

        node_ids = [evidence.source_node_id]
        if evidence.target_node_id is not None:
            node_ids.append(evidence.target_node_id)
        await self._validate_node_repositories(evidence.repository_id, node_ids)
        if evidence.target_edge_id is not None:
            target_edge = await self.session.get(GraphEdge, evidence.target_edge_id)
            if target_edge is None or target_edge.repository_id != evidence.repository_id:
                raise GraphInvariantError("Evidence target edge is outside the repository graph")

        values = {
            "repository_id": evidence.repository_id,
            "repository_version_id": evidence.repository_version_id,
            "canonical_key": evidence.canonical_key,
            "source_node_id": evidence.source_node_id,
            "target_node_id": evidence.target_node_id,
            "target_edge_id": evidence.target_edge_id,
            "evidence_type": evidence.evidence_type.value,
            "relationship": evidence.relationship.value if evidence.relationship else None,
            "excerpt": evidence.excerpt,
            "source_url": evidence.source_url,
            "start_line": evidence.start_line,
            "end_line": evidence.end_line,
            "confidence": evidence.confidence,
            "provenance": evidence.provenance,
            "details": evidence.metadata,
        }
        insert_statement = insert(GraphEvidence).values(**values)
        statement = insert_statement.on_conflict_do_update(
            constraint="uq_evidence_repository_canonical_key",
            set_={
                "repository_version_id": insert_statement.excluded.repository_version_id,
                "source_node_id": insert_statement.excluded.source_node_id,
                "target_node_id": insert_statement.excluded.target_node_id,
                "target_edge_id": insert_statement.excluded.target_edge_id,
                "evidence_type": insert_statement.excluded.evidence_type,
                "relationship": insert_statement.excluded.relationship,
                "excerpt": insert_statement.excluded.excerpt,
                "source_url": insert_statement.excluded.source_url,
                "start_line": insert_statement.excluded.start_line,
                "end_line": insert_statement.excluded.end_line,
                "confidence": insert_statement.excluded.confidence,
                "provenance": insert_statement.excluded.provenance,
                "metadata": insert_statement.excluded.metadata,
                "updated_at": insert_statement.excluded.updated_at,
            },
        ).returning(GraphEvidence)
        result = await self.session.execute(statement)
        return result.scalar_one()

    async def upsert_metric(self, metric: GraphMetricInput) -> GraphMetric:
        _validate_required(metric.metric_name, "metric_name")
        _validate_required(metric.scope_key, "scope_key")
        _validate_required(metric.algorithm_version, "algorithm_version")
        if not isfinite(metric.value):
            raise GraphInvariantError("metric value must be finite")
        if metric.node_id is not None:
            await self._validate_node_repositories(metric.repository_id, (metric.node_id,))

        values = {
            "repository_id": metric.repository_id,
            "repository_version_id": metric.repository_version_id,
            "node_id": metric.node_id,
            "metric_name": metric.metric_name,
            "scope_key": metric.scope_key,
            "value": metric.value,
            "algorithm_version": metric.algorithm_version,
            "details": metric.metadata,
        }
        insert_statement = insert(GraphMetric).values(**values)
        statement = insert_statement.on_conflict_do_update(
            constraint="uq_graph_metrics_version_metric_scope_algorithm",
            set_={
                "repository_id": insert_statement.excluded.repository_id,
                "node_id": insert_statement.excluded.node_id,
                "value": insert_statement.excluded.value,
                "metadata": insert_statement.excluded.metadata,
                "updated_at": insert_statement.excluded.updated_at,
            },
        ).returning(GraphMetric)
        result = await self.session.execute(statement)
        return result.scalar_one()

    async def load_for_analysis(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        max_nodes: int = MAX_ANALYSIS_NODES,
        max_edges: int = MAX_ANALYSIS_EDGES,
    ) -> GraphSnapshot:
        if max_nodes < 1 or max_edges < 1:
            raise GraphInvariantError("Graph analysis limits must be positive")
        node_result = await self.session.execute(
            select(GraphNode)
            .where(
                GraphNode.repository_id == repository_id,
                GraphNode.knowledge_kind == KnowledgeKind.DETERMINISTIC,
                or_(
                    GraphNode.repository_version_id == repository_version_id,
                    GraphNode.repository_version_id.is_(None),
                ),
            )
            .order_by(GraphNode.canonical_key)
            .limit(max_nodes + 1)
        )
        nodes = node_result.scalars().all()
        if len(nodes) > max_nodes:
            raise GraphAnalysisLimitError(
                f"Graph analysis exceeds the {max_nodes} node safety limit"
            )

        edge_result = await self.session.execute(
            select(GraphEdge)
            .where(
                GraphEdge.repository_id == repository_id,
                GraphEdge.knowledge_kind == KnowledgeKind.DETERMINISTIC,
                or_(
                    GraphEdge.repository_version_id == repository_version_id,
                    GraphEdge.repository_version_id.is_(None),
                ),
            )
            .order_by(GraphEdge.relationship_type, GraphEdge.id)
            .limit(max_edges + 1)
        )
        edges = edge_result.scalars().all()
        if len(edges) > max_edges:
            raise GraphAnalysisLimitError(
                f"Graph analysis exceeds the {max_edges} edge safety limit"
            )
        node_ids = {node.id for node in nodes}
        if any(
            edge.source_node_id not in node_ids or edge.target_node_id not in node_ids
            for edge in edges
        ):
            raise GraphInvariantError("Analysis graph contains an edge outside its snapshot")
        return GraphSnapshot(nodes=nodes, edges=edges)

    async def replace_metrics(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        algorithm_version: str,
        metrics: Sequence[GraphMetricInput],
    ) -> int:
        _validate_required(algorithm_version, "algorithm_version")
        for metric in metrics:
            if (
                metric.repository_id != repository_id
                or metric.repository_version_id != repository_version_id
                or metric.algorithm_version != algorithm_version
            ):
                raise GraphInvariantError("Replacement metrics must share one analysis scope")
            _validate_required(metric.metric_name, "metric_name")
            _validate_required(metric.scope_key, "scope_key")
            if not isfinite(metric.value):
                raise GraphInvariantError("metric value must be finite")

        node_ids = tuple({metric.node_id for metric in metrics if metric.node_id is not None})
        if node_ids:
            await self._validate_node_repositories(repository_id, node_ids)

        await self.session.execute(
            delete(GraphMetric).where(
                GraphMetric.repository_id == repository_id,
                GraphMetric.repository_version_id == repository_version_id,
                GraphMetric.algorithm_version == algorithm_version,
            )
        )
        if not metrics:
            return 0

        persisted_count = 0
        for offset in range(0, len(metrics), MAX_METRIC_BATCH_SIZE):
            batch = metrics[offset : offset + MAX_METRIC_BATCH_SIZE]
            values = [
                {
                    "repository_id": metric.repository_id,
                    "repository_version_id": metric.repository_version_id,
                    "node_id": metric.node_id,
                    "metric_name": metric.metric_name,
                    "scope_key": metric.scope_key,
                    "value": metric.value,
                    "algorithm_version": metric.algorithm_version,
                    "details": metric.metadata,
                }
                for metric in batch
            ]
            insert_statement = insert(GraphMetric).values(values)
            statement = insert_statement.on_conflict_do_update(
                constraint="uq_graph_metrics_version_metric_scope_algorithm",
                set_={
                    "repository_id": insert_statement.excluded.repository_id,
                    "node_id": insert_statement.excluded.node_id,
                    "value": insert_statement.excluded.value,
                    "metadata": insert_statement.excluded.metadata,
                    "updated_at": insert_statement.excluded.updated_at,
                },
            )
            await self.session.execute(statement)
            persisted_count += len(batch)
        return persisted_count

    async def neighbors(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        node_id: UUID,
        depth: int = 1,
        limit: int = 100,
        edge_limit: int = 1_000,
        metric_limit: int = 2_000,
        entity_types: Sequence[EntityType] = (),
        relationship_types: Sequence[RelationshipType] = (),
        knowledge_kinds: Sequence[KnowledgeKind] = (),
        metric_names: Sequence[str] = (),
        include_metrics: bool = True,
    ) -> GraphSnapshot:
        _validate_query_limits(
            node_limit=limit,
            edge_limit=edge_limit,
            metric_limit=metric_limit,
        )
        if not 1 <= depth <= 3:
            raise GraphInvariantError("Graph traversal depth must be between 1 and 3")

        root_result = await self.session.execute(
            select(GraphNode).where(
                GraphNode.id == node_id,
                GraphNode.repository_id == repository_id,
                or_(
                    GraphNode.repository_version_id == repository_version_id,
                    GraphNode.repository_version_id.is_(None),
                ),
            )
        )
        root = root_result.scalar_one_or_none()
        if root is None:
            raise GraphNodeNotFoundError

        nodes_by_id = {root.id: root}
        frontier = {root.id}
        nodes_truncated = False
        traversal_edges_truncated = False
        for _ in range(depth):
            edge_statement = select(GraphEdge).where(
                GraphEdge.repository_id == repository_id,
                or_(
                    GraphEdge.repository_version_id == repository_version_id,
                    GraphEdge.repository_version_id.is_(None),
                ),
                or_(
                    GraphEdge.source_node_id.in_(frontier),
                    GraphEdge.target_node_id.in_(frontier),
                ),
            )
            if relationship_types:
                edge_statement = edge_statement.where(
                    GraphEdge.relationship_type.in_(
                        relationship.value for relationship in relationship_types
                    )
                )
            if knowledge_kinds:
                edge_statement = edge_statement.where(
                    GraphEdge.knowledge_kind.in_(kind.value for kind in knowledge_kinds)
                )
            edge_result = await self.session.execute(
                edge_statement.order_by(GraphEdge.relationship_type, GraphEdge.id).limit(
                    edge_limit + 1
                )
            )
            traversal_edges = edge_result.scalars().all()
            if len(traversal_edges) > edge_limit:
                traversal_edges_truncated = True
                traversal_edges = traversal_edges[:edge_limit]

            candidate_ids = {
                candidate_id
                for edge in traversal_edges
                for candidate_id in (edge.source_node_id, edge.target_node_id)
                if candidate_id not in nodes_by_id
            }
            if not candidate_ids:
                break
            remaining = limit - len(nodes_by_id)
            if remaining == 0:
                nodes_truncated = True
                break

            node_statement = select(GraphNode).where(
                GraphNode.id.in_(candidate_ids),
                GraphNode.repository_id == repository_id,
                or_(
                    GraphNode.repository_version_id == repository_version_id,
                    GraphNode.repository_version_id.is_(None),
                ),
            )
            if entity_types:
                node_statement = node_statement.where(
                    GraphNode.entity_type.in_(entity.value for entity in entity_types)
                )
            if knowledge_kinds:
                node_statement = node_statement.where(
                    GraphNode.knowledge_kind.in_(kind.value for kind in knowledge_kinds)
                )
            node_result = await self.session.execute(
                node_statement.order_by(GraphNode.canonical_key).limit(remaining + 1)
            )
            discovered = node_result.scalars().all()
            if len(discovered) > remaining:
                nodes_truncated = True
                discovered = discovered[:remaining]
            frontier = {node.id for node in discovered}
            nodes_by_id.update((node.id, node) for node in discovered)
            if not frontier or nodes_truncated:
                break

        nodes = sorted(nodes_by_id.values(), key=lambda node: node.canonical_key)
        edges, edges_truncated = await self._edges_between(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            node_ids=tuple(nodes_by_id),
            relationship_types=relationship_types,
            knowledge_kinds=knowledge_kinds,
            limit=edge_limit,
        )
        metrics, metrics_truncated = await self._metrics_for_nodes(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            node_ids=tuple(nodes_by_id),
            metric_names=metric_names,
            limit=metric_limit,
            include=include_metrics,
        )
        return GraphSnapshot(
            nodes=nodes,
            edges=edges,
            metrics=metrics,
            nodes_truncated=nodes_truncated,
            edges_truncated=edges_truncated or traversal_edges_truncated,
            metrics_truncated=metrics_truncated,
        )

    async def subgraph(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        limit: int = MAX_GRAPH_RESULT_NODES,
        edge_limit: int = 1_000,
        metric_limit: int = 2_000,
        entity_types: Sequence[EntityType] = (),
        relationship_types: Sequence[RelationshipType] = (),
        knowledge_kinds: Sequence[KnowledgeKind] = (),
        metric_names: Sequence[str] = (),
        include_metrics: bool = True,
    ) -> GraphSnapshot:
        _validate_query_limits(
            node_limit=limit,
            edge_limit=edge_limit,
            metric_limit=metric_limit,
        )
        node_statement = select(GraphNode).where(
            GraphNode.repository_id == repository_id,
            or_(
                GraphNode.repository_version_id == repository_version_id,
                GraphNode.repository_version_id.is_(None),
            ),
        )
        if entity_types:
            node_statement = node_statement.where(
                GraphNode.entity_type.in_(entity.value for entity in entity_types)
            )
        if knowledge_kinds:
            node_statement = node_statement.where(
                GraphNode.knowledge_kind.in_(kind.value for kind in knowledge_kinds)
            )
        node_result = await self.session.execute(
            node_statement.order_by(GraphNode.canonical_key).limit(limit + 1)
        )
        nodes = node_result.scalars().all()
        nodes_truncated = len(nodes) > limit
        nodes = nodes[:limit]
        node_ids = tuple(node.id for node in nodes)
        edges, edges_truncated = await self._edges_between(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            node_ids=node_ids,
            relationship_types=relationship_types,
            knowledge_kinds=knowledge_kinds,
            limit=edge_limit,
        )
        metrics, metrics_truncated = await self._metrics_for_nodes(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            node_ids=node_ids,
            metric_names=metric_names,
            limit=metric_limit,
            include=include_metrics,
        )
        return GraphSnapshot(
            nodes=nodes,
            edges=edges,
            metrics=metrics,
            nodes_truncated=nodes_truncated,
            edges_truncated=edges_truncated,
            metrics_truncated=metrics_truncated,
        )

    async def _edges_between(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        node_ids: Sequence[UUID],
        relationship_types: Sequence[RelationshipType],
        knowledge_kinds: Sequence[KnowledgeKind],
        limit: int,
    ) -> tuple[Sequence[GraphEdge], bool]:
        if not node_ids:
            return (), False
        statement = select(GraphEdge).where(
            GraphEdge.repository_id == repository_id,
            or_(
                GraphEdge.repository_version_id == repository_version_id,
                GraphEdge.repository_version_id.is_(None),
            ),
            GraphEdge.source_node_id.in_(node_ids),
            GraphEdge.target_node_id.in_(node_ids),
        )
        if relationship_types:
            statement = statement.where(
                GraphEdge.relationship_type.in_(
                    relationship.value for relationship in relationship_types
                )
            )
        if knowledge_kinds:
            statement = statement.where(
                GraphEdge.knowledge_kind.in_(kind.value for kind in knowledge_kinds)
            )
        result = await self.session.execute(
            statement.order_by(GraphEdge.relationship_type, GraphEdge.id).limit(limit + 1)
        )
        edges = result.scalars().all()
        return edges[:limit], len(edges) > limit

    async def _metrics_for_nodes(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        node_ids: Sequence[UUID],
        metric_names: Sequence[str],
        limit: int,
        include: bool,
    ) -> tuple[Sequence[GraphMetric], bool]:
        if not include:
            return (), False
        node_condition: ColumnElement[bool] = GraphMetric.node_id.is_(None)
        if node_ids:
            node_condition = or_(node_condition, GraphMetric.node_id.in_(node_ids))
        statement = select(GraphMetric).where(
            GraphMetric.repository_id == repository_id,
            GraphMetric.repository_version_id == repository_version_id,
            node_condition,
        )
        if metric_names:
            statement = statement.where(GraphMetric.metric_name.in_(metric_names))
        result = await self.session.execute(
            statement.order_by(
                GraphMetric.metric_name,
                GraphMetric.scope_key,
                GraphMetric.algorithm_version,
            ).limit(limit + 1)
        )
        metrics = result.scalars().all()
        return metrics[:limit], len(metrics) > limit

    async def _validate_node_repositories(
        self,
        repository_id: UUID,
        node_ids: Sequence[UUID],
    ) -> None:
        unique_ids = set(node_ids)
        result = await self.session.execute(
            select(GraphNode.id, GraphNode.repository_id).where(GraphNode.id.in_(unique_ids))
        )
        repositories = {node_id: node_repository_id for node_id, node_repository_id in result.all()}
        if set(repositories) != unique_ids or any(
            value != repository_id for value in repositories.values()
        ):
            raise GraphInvariantError("Graph nodes must exist in the same repository graph")


def _validate_confidence(confidence: float) -> None:
    if not 0 <= confidence <= 1:
        raise GraphInvariantError("confidence must be between 0 and 1")


def _validate_required(value: str, field_name: str) -> None:
    if not value.strip():
        raise GraphInvariantError(f"{field_name} cannot be empty")


def _validate_provenance(provenance: dict[str, object]) -> None:
    if not provenance:
        raise GraphInvariantError("Graph facts require provenance")


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= MAX_GRAPH_RESULT_NODES:
        raise GraphInvariantError(
            f"Graph result limit must be between 1 and {MAX_GRAPH_RESULT_NODES}"
        )


def _validate_query_limits(*, node_limit: int, edge_limit: int, metric_limit: int) -> None:
    _validate_limit(node_limit)
    if not 1 <= edge_limit <= MAX_GRAPH_RESULT_EDGES:
        raise GraphInvariantError(
            f"Graph edge limit must be between 1 and {MAX_GRAPH_RESULT_EDGES}"
        )
    if not 1 <= metric_limit <= MAX_GRAPH_RESULT_METRICS:
        raise GraphInvariantError(
            f"Graph metric limit must be between 1 and {MAX_GRAPH_RESULT_METRICS}"
        )
