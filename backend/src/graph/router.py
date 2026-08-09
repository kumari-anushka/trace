from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from src.graph.dependencies import get_graph_service
from src.graph.models import EntityType, KnowledgeKind, RelationshipType
from src.graph.repository import (
    MAX_GRAPH_RESULT_EDGES,
    MAX_GRAPH_RESULT_EVIDENCE,
    MAX_GRAPH_RESULT_METRICS,
    MAX_GRAPH_RESULT_NODES,
)
from src.graph.schemas import GraphEvidenceListResponse, GraphEvidenceResponse, GraphResponse
from src.graph.service import GraphService

router = APIRouter(
    prefix="/repositories/{repository_id}/versions/{repository_version_id}/graph",
    tags=["Graph"],
)

GraphServiceDependency = Annotated[GraphService, Depends(get_graph_service)]
NodeLimit = Annotated[int, Query(ge=1, le=MAX_GRAPH_RESULT_NODES)]
EdgeLimit = Annotated[int, Query(ge=1, le=MAX_GRAPH_RESULT_EDGES)]
MetricLimit = Annotated[int, Query(ge=1, le=MAX_GRAPH_RESULT_METRICS)]
EntityTypeFilter = Annotated[list[EntityType] | None, Query(alias="entity_type")]
RelationshipTypeFilter = Annotated[list[RelationshipType] | None, Query(alias="relationship_type")]
KnowledgeKindFilter = Annotated[list[KnowledgeKind] | None, Query(alias="knowledge_kind")]
MetricNameFilter = Annotated[list[str] | None, Query(alias="metric_name", max_length=20)]
EvidenceLimit = Annotated[int, Query(ge=1, le=MAX_GRAPH_RESULT_EVIDENCE)]


@router.get("", response_model=GraphResponse)
async def get_graph(
    repository_id: UUID,
    repository_version_id: UUID,
    service: GraphServiceDependency,
    limit: NodeLimit = 200,
    edge_limit: EdgeLimit = 1_000,
    metric_limit: MetricLimit = 2_000,
    entity_types: EntityTypeFilter = None,
    relationship_types: RelationshipTypeFilter = None,
    knowledge_kinds: KnowledgeKindFilter = None,
    metric_names: MetricNameFilter = None,
    include_metrics: bool = True,
) -> GraphResponse:
    snapshot = await service.get_graph(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        limit=limit,
        edge_limit=edge_limit,
        metric_limit=metric_limit,
        entity_types=entity_types or (),
        relationship_types=relationship_types or (),
        knowledge_kinds=knowledge_kinds or (),
        metric_names=metric_names or (),
        include_metrics=include_metrics,
    )
    return GraphResponse.from_snapshot(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        snapshot=snapshot,
    )


@router.get("/nodes/{node_id}/neighbors", response_model=GraphResponse)
async def get_graph_neighbors(
    repository_id: UUID,
    repository_version_id: UUID,
    node_id: UUID,
    service: GraphServiceDependency,
    depth: Annotated[int, Query(ge=1, le=3)] = 1,
    limit: NodeLimit = 100,
    edge_limit: EdgeLimit = 1_000,
    metric_limit: MetricLimit = 2_000,
    entity_types: EntityTypeFilter = None,
    relationship_types: RelationshipTypeFilter = None,
    knowledge_kinds: KnowledgeKindFilter = None,
    metric_names: MetricNameFilter = None,
    include_metrics: bool = True,
) -> GraphResponse:
    snapshot = await service.get_neighbors(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        node_id=node_id,
        depth=depth,
        limit=limit,
        edge_limit=edge_limit,
        metric_limit=metric_limit,
        entity_types=entity_types or (),
        relationship_types=relationship_types or (),
        knowledge_kinds=knowledge_kinds or (),
        metric_names=metric_names or (),
        include_metrics=include_metrics,
    )
    return GraphResponse.from_snapshot(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        root_node_id=node_id,
        depth=depth,
        snapshot=snapshot,
    )


@router.get("/evidence", response_model=GraphEvidenceListResponse)
async def get_graph_evidence(
    repository_id: UUID,
    repository_version_id: UUID,
    service: GraphServiceDependency,
    target_node_id: UUID | None = None,
    target_edge_id: UUID | None = None,
    limit: EvidenceLimit = 100,
) -> GraphEvidenceListResponse:
    evidence, truncated = await service.get_evidence(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        target_node_id=target_node_id,
        target_edge_id=target_edge_id,
        limit=limit,
    )
    return GraphEvidenceListResponse(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        count=len(evidence),
        truncated=truncated,
        evidence=[GraphEvidenceResponse.model_validate(item) for item in evidence],
    )
