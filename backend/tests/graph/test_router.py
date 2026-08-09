from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.exceptions import GraphNodeNotFoundError
from src.core.ontology import ONTOLOGY_VERSION
from src.graph.dependencies import get_graph_service
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
from src.graph.repository import GraphSnapshot
from src.graph.service import GraphService


def graph_snapshot() -> tuple[GraphSnapshot, GraphNode]:
    now = datetime.now(UTC)
    repository_id = uuid4()
    repository_version_id = uuid4()
    source = GraphNode(
        id=uuid4(),
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        entity_type=EntityType.FILE.value,
        canonical_key="file:src/main.py",
        name="main.py",
        description=None,
        knowledge_kind=KnowledgeKind.DETERMINISTIC.value,
        confidence=1.0,
        provenance={"parser": "python_ast"},
        details={"path": "src/main.py"},
        ontology_version=ONTOLOGY_VERSION,
        created_at=now,
        updated_at=now,
    )
    target = GraphNode(
        id=uuid4(),
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        entity_type=EntityType.FILE.value,
        canonical_key="file:src/helper.py",
        name="helper.py",
        description=None,
        knowledge_kind=KnowledgeKind.DETERMINISTIC.value,
        confidence=1.0,
        provenance={"parser": "python_ast"},
        details={"path": "src/helper.py"},
        ontology_version=ONTOLOGY_VERSION,
        created_at=now,
        updated_at=now,
    )
    edge = GraphEdge(
        id=uuid4(),
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        source_node_id=source.id,
        target_node_id=target.id,
        relationship_type=RelationshipType.IMPORTS.value,
        knowledge_kind=KnowledgeKind.DETERMINISTIC.value,
        confidence=1.0,
        provenance={"parser": "python_ast"},
        details={"module": "helper"},
        ontology_version=ONTOLOGY_VERSION,
        created_at=now,
        updated_at=now,
    )
    metric = GraphMetric(
        id=uuid4(),
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        node_id=source.id,
        metric_name="degree_centrality",
        scope_key=source.canonical_key,
        value=1.0,
        algorithm_version="networkx-test",
        details={"projection": "full_undirected_graph"},
        created_at=now,
        updated_at=now,
    )
    return (
        GraphSnapshot(
            nodes=(source, target),
            edges=(edge,),
            metrics=(metric,),
            nodes_truncated=True,
        ),
        source,
    )


def override_graph_service(app: FastAPI, service: AsyncMock) -> None:
    def dependency_override() -> GraphService:
        return cast(GraphService, service)

    app.dependency_overrides[get_graph_service] = dependency_override


def test_get_graph_returns_bounded_filtered_snapshot(app: FastAPI, client: TestClient) -> None:
    snapshot, _ = graph_snapshot()
    service = AsyncMock(spec=GraphService)
    service.get_graph.return_value = snapshot
    override_graph_service(app, service)

    response = client.get(
        (
            f"/api/repositories/{snapshot.nodes[0].repository_id}/versions/"
            f"{snapshot.nodes[0].repository_version_id}/graph"
        ),
        params=[
            ("limit", "10"),
            ("edge_limit", "20"),
            ("metric_limit", "30"),
            ("entity_type", "file"),
            ("relationship_type", "IMPORTS"),
            ("knowledge_kind", "deterministic"),
            ("metric_name", "degree_centrality"),
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["node_count"] == 2
    assert body["edge_count"] == 1
    assert body["metric_count"] == 1
    assert body["nodes_truncated"] is True
    assert body["nodes"][0]["metadata"] == {"path": "src/main.py"}
    assert body["edges"][0]["relationship_type"] == "IMPORTS"
    assert body["metrics"][0]["metric_name"] == "degree_centrality"
    service.get_graph.assert_awaited_once_with(
        repository_id=snapshot.nodes[0].repository_id,
        repository_version_id=snapshot.nodes[0].repository_version_id,
        limit=10,
        edge_limit=20,
        metric_limit=30,
        entity_types=[EntityType.FILE],
        relationship_types=[RelationshipType.IMPORTS],
        knowledge_kinds=[KnowledgeKind.DETERMINISTIC],
        metric_names=["degree_centrality"],
        include_metrics=True,
    )


def test_get_neighbors_returns_root_and_depth(app: FastAPI, client: TestClient) -> None:
    snapshot, root = graph_snapshot()
    service = AsyncMock(spec=GraphService)
    service.get_neighbors.return_value = snapshot
    override_graph_service(app, service)

    response = client.get(
        (
            f"/api/repositories/{root.repository_id}/versions/"
            f"{root.repository_version_id}/graph/nodes/{root.id}/neighbors"
        ),
        params={"depth": 3, "include_metrics": False},
    )

    assert response.status_code == 200
    assert response.json()["root_node_id"] == str(root.id)
    assert response.json()["depth"] == 3
    service.get_neighbors.assert_awaited_once_with(
        repository_id=root.repository_id,
        repository_version_id=root.repository_version_id,
        node_id=root.id,
        depth=3,
        limit=100,
        edge_limit=1_000,
        metric_limit=2_000,
        entity_types=(),
        relationship_types=(),
        knowledge_kinds=(),
        metric_names=(),
        include_metrics=False,
    )


def test_graph_query_rejects_limits_above_caps(app: FastAPI, client: TestClient) -> None:
    service = AsyncMock(spec=GraphService)
    override_graph_service(app, service)
    repository_id = uuid4()
    repository_version_id = uuid4()

    response = client.get(
        f"/api/repositories/{repository_id}/versions/{repository_version_id}/graph",
        params={"limit": 501},
    )

    assert response.status_code == 422
    assert response.json()["message"] == "Invalid request"
    service.get_graph.assert_not_awaited()


def test_neighbor_query_rejects_depth_above_cap(app: FastAPI, client: TestClient) -> None:
    service = AsyncMock(spec=GraphService)
    override_graph_service(app, service)

    response = client.get(
        (f"/api/repositories/{uuid4()}/versions/{uuid4()}/graph/nodes/{uuid4()}/neighbors"),
        params={"depth": 4},
    )

    assert response.status_code == 422
    service.get_neighbors.assert_not_awaited()


def test_neighbor_query_returns_404_for_missing_node(app: FastAPI, client: TestClient) -> None:
    service = AsyncMock(spec=GraphService)
    service.get_neighbors.side_effect = GraphNodeNotFoundError()
    override_graph_service(app, service)

    response = client.get(
        f"/api/repositories/{uuid4()}/versions/{uuid4()}/graph/nodes/{uuid4()}/neighbors"
    )

    assert response.status_code == 404
    assert response.json() == {"message": "Graph node not found"}


def test_get_evidence_returns_bounded_source_details(app: FastAPI, client: TestClient) -> None:
    snapshot, root = graph_snapshot()
    edge = snapshot.edges[0]
    now = datetime.now(UTC)
    evidence = GraphEvidence(
        id=uuid4(),
        repository_id=root.repository_id,
        repository_version_id=root.repository_version_id,
        canonical_key="evidence:main-import",
        source_node_id=root.id,
        target_node_id=None,
        target_edge_id=edge.id,
        evidence_type=EvidenceType.SOURCE_SPAN.value,
        relationship=RelationshipType.IMPORTS.value,
        excerpt="from app import helper",
        source_url="https://github.test/acme/trace/blob/sha/src/main.py",
        start_line=3,
        end_line=3,
        confidence=1.0,
        provenance={"parser": "python_ast"},
        details={"path": "src/main.py"},
        created_at=now,
        updated_at=now,
    )
    service = AsyncMock(spec=GraphService)
    service.get_evidence.return_value = ((evidence,), False)
    override_graph_service(app, service)

    response = client.get(
        (
            f"/api/repositories/{root.repository_id}/versions/"
            f"{root.repository_version_id}/graph/evidence"
        ),
        params={"target_edge_id": str(edge.id), "limit": 25},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["truncated"] is False
    assert body["evidence"][0]["excerpt"] == "from app import helper"
    assert body["evidence"][0]["metadata"] == {"path": "src/main.py"}
    service.get_evidence.assert_awaited_once_with(
        repository_id=root.repository_id,
        repository_version_id=root.repository_version_id,
        target_node_id=None,
        target_edge_id=edge.id,
        limit=25,
    )
