from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.graph.models import EntityType, KnowledgeKind, RelationshipType
from src.graph.repository import GraphSnapshot


class GraphNodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    repository_version_id: UUID | None
    entity_type: EntityType
    canonical_key: str
    name: str
    description: str | None
    knowledge_kind: KnowledgeKind
    confidence: float
    provenance: dict[str, object]
    metadata: dict[str, object] = Field(validation_alias="details")
    ontology_version: str
    created_at: datetime
    updated_at: datetime


class GraphEdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    repository_version_id: UUID | None
    source_node_id: UUID
    target_node_id: UUID
    relationship_type: RelationshipType
    knowledge_kind: KnowledgeKind
    confidence: float
    provenance: dict[str, object]
    metadata: dict[str, object] = Field(validation_alias="details")
    ontology_version: str
    created_at: datetime
    updated_at: datetime


class GraphMetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    repository_version_id: UUID
    node_id: UUID | None
    metric_name: str
    scope_key: str
    value: float
    algorithm_version: str
    metadata: dict[str, object] = Field(validation_alias="details")
    created_at: datetime
    updated_at: datetime


class GraphResponse(BaseModel):
    repository_id: UUID
    repository_version_id: UUID
    root_node_id: UUID | None = None
    depth: int | None = None
    node_count: int
    edge_count: int
    metric_count: int
    nodes_truncated: bool
    edges_truncated: bool
    metrics_truncated: bool
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]
    metrics: list[GraphMetricResponse]

    @classmethod
    def from_snapshot(
        cls,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        snapshot: GraphSnapshot,
        root_node_id: UUID | None = None,
        depth: int | None = None,
    ) -> GraphResponse:
        return cls(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            root_node_id=root_node_id,
            depth=depth,
            node_count=len(snapshot.nodes),
            edge_count=len(snapshot.edges),
            metric_count=len(snapshot.metrics),
            nodes_truncated=snapshot.nodes_truncated,
            edges_truncated=snapshot.edges_truncated,
            metrics_truncated=snapshot.metrics_truncated,
            nodes=[GraphNodeResponse.model_validate(node) for node in snapshot.nodes],
            edges=[GraphEdgeResponse.model_validate(edge) for edge in snapshot.edges],
            metrics=[GraphMetricResponse.model_validate(metric) for metric in snapshot.metrics],
        )
