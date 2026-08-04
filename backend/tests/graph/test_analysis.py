from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.core.ontology import ONTOLOGY_VERSION
from src.graph.analysis import (
    GraphAnalysisBuilder,
    GraphAnalysisRepository,
    NetworkXGraphAnalyzer,
)
from src.graph.models import (
    EntityType,
    GraphEdge,
    GraphNode,
    KnowledgeKind,
    RelationshipType,
)
from src.graph.repository import GraphSnapshot


def graph_node(*, repository_id: UUID, repository_version_id: UUID, key: str) -> GraphNode:
    return GraphNode(
        id=uuid4(),
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        entity_type=EntityType.FILE.value,
        canonical_key=key,
        name=f"{key}.py",
        description=None,
        knowledge_kind=KnowledgeKind.DETERMINISTIC.value,
        confidence=1.0,
        provenance={"parser": "test"},
        details={"path": f"{key}.py"},
        ontology_version=ONTOLOGY_VERSION,
    )


def import_edge(
    *, repository_id: UUID, repository_version_id: UUID, source: GraphNode, target: GraphNode
) -> GraphEdge:
    return GraphEdge(
        id=uuid4(),
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        source_node_id=source.id,
        target_node_id=target.id,
        relationship_type=RelationshipType.IMPORTS.value,
        knowledge_kind=KnowledgeKind.DETERMINISTIC.value,
        confidence=1.0,
        provenance={"parser": "test"},
        details={},
        ontology_version=ONTOLOGY_VERSION,
    )


def analysis_snapshot() -> tuple[UUID, UUID, GraphSnapshot]:
    repository_id = uuid4()
    repository_version_id = uuid4()
    nodes = {
        key: graph_node(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            key=key,
        )
        for key in ("a", "b", "c", "d", "e")
    }
    edges = (
        import_edge(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            source=nodes["a"],
            target=nodes["b"],
        ),
        import_edge(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            source=nodes["b"],
            target=nodes["c"],
        ),
        import_edge(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            source=nodes["c"],
            target=nodes["a"],
        ),
        import_edge(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            source=nodes["c"],
            target=nodes["d"],
        ),
    )
    return (
        repository_id,
        repository_version_id,
        GraphSnapshot(nodes=tuple(nodes.values()), edges=edges),
    )


def test_networkx_analysis_detects_structure_and_dependency_cycle() -> None:
    repository_id, repository_version_id, snapshot = analysis_snapshot()

    result = NetworkXGraphAnalyzer().analyze(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        snapshot=snapshot,
    )

    assert result.summary.nodes == 5
    assert result.summary.edges == 4
    assert result.summary.connected_components == 2
    assert result.summary.communities == 3
    assert result.summary.bridges == 1
    assert result.summary.dependency_cycles == 1
    assert result.summary.metrics == 23
    assert {metric.metric_name for metric in result.metrics} >= {
        "degree_centrality",
        "connected_component_membership",
        "community_membership",
        "bridge",
        "dependency_cycle",
    }
    cycle_metric = next(
        metric for metric in result.metrics if metric.metric_name == "dependency_cycle"
    )
    assert cycle_metric.value == 3.0


@pytest.mark.asyncio
async def test_analysis_builder_replaces_one_algorithm_version_atomically() -> None:
    repository_id, repository_version_id, snapshot = analysis_snapshot()
    repository = AsyncMock(spec=GraphAnalysisRepository)
    repository.load_for_analysis.return_value = snapshot
    builder = GraphAnalysisBuilder(repository=repository)

    summary = await builder.build(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
    )

    assert summary.metrics == 23
    repository.replace_metrics.assert_awaited_once()
    call = repository.replace_metrics.await_args.kwargs
    assert call["repository_id"] == repository_id
    assert call["repository_version_id"] == repository_version_id
    assert call["algorithm_version"] == builder.analyzer.algorithm_version
    assert len(call["metrics"]) == summary.metrics
