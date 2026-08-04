from collections.abc import Sequence
from uuid import UUID, uuid4

from src.graph.models import (
    EntityType,
    GraphEdge,
    GraphEvidence,
    GraphMetric,
    GraphNode,
    KnowledgeKind,
    RelationshipType,
)
from src.graph.repository import (
    GraphEdgeInput,
    GraphEvidenceInput,
    GraphMetricInput,
    GraphNodeInput,
    GraphSnapshot,
)


class MemoryGraphRepository:
    def __init__(self) -> None:
        self.nodes: dict[tuple[UUID, str], GraphNode] = {}
        self.edges: dict[tuple[UUID, UUID, UUID, str], GraphEdge] = {}
        self.evidence: dict[tuple[UUID, str], GraphEvidence] = {}

    async def upsert_node(self, node: GraphNodeInput) -> GraphNode:
        key = (node.repository_id, node.canonical_key)
        persisted = GraphNode(
            id=self.nodes[key].id if key in self.nodes else uuid4(),
            repository_id=node.repository_id,
            repository_version_id=node.repository_version_id,
            entity_type=node.entity_type.value,
            canonical_key=node.canonical_key,
            name=node.name,
            description=node.description,
            knowledge_kind=node.knowledge_kind.value,
            confidence=node.confidence,
            provenance=node.provenance,
            details=node.metadata,
            ontology_version=node.ontology_version,
        )
        self.nodes[key] = persisted
        return persisted

    async def upsert_edge(self, edge: GraphEdgeInput) -> GraphEdge:
        key = (
            edge.repository_id,
            edge.source_node_id,
            edge.target_node_id,
            edge.relationship_type.value,
        )
        persisted = GraphEdge(
            id=self.edges[key].id if key in self.edges else uuid4(),
            repository_id=edge.repository_id,
            repository_version_id=edge.repository_version_id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            relationship_type=edge.relationship_type.value,
            knowledge_kind=edge.knowledge_kind.value,
            confidence=edge.confidence,
            provenance=edge.provenance,
            details=edge.metadata,
            ontology_version=edge.ontology_version,
        )
        self.edges[key] = persisted
        return persisted

    async def upsert_evidence(self, evidence: GraphEvidenceInput) -> GraphEvidence:
        key = (evidence.repository_id, evidence.canonical_key)
        persisted = GraphEvidence(
            id=self.evidence[key].id if key in self.evidence else uuid4(),
            repository_id=evidence.repository_id,
            repository_version_id=evidence.repository_version_id,
            canonical_key=evidence.canonical_key,
            source_node_id=evidence.source_node_id,
            target_node_id=evidence.target_node_id,
            target_edge_id=evidence.target_edge_id,
            evidence_type=evidence.evidence_type.value,
            relationship=evidence.relationship.value if evidence.relationship else None,
            excerpt=evidence.excerpt,
            source_url=evidence.source_url,
            start_line=evidence.start_line,
            end_line=evidence.end_line,
            confidence=evidence.confidence,
            provenance=evidence.provenance,
            details=evidence.metadata,
        )
        self.evidence[key] = persisted
        return persisted

    async def upsert_metric(self, metric: GraphMetricInput) -> GraphMetric:
        raise NotImplementedError

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
        raise NotImplementedError

    async def subgraph(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        limit: int = 500,
        edge_limit: int = 1_000,
        metric_limit: int = 2_000,
        entity_types: Sequence[EntityType] = (),
        relationship_types: Sequence[RelationshipType] = (),
        knowledge_kinds: Sequence[KnowledgeKind] = (),
        metric_names: Sequence[str] = (),
        include_metrics: bool = True,
    ) -> GraphSnapshot:
        raise NotImplementedError
