from dataclasses import asdict
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from src.graph.filesystem import (
    CONTAINS,
    FilesystemGraphBuilder,
    SourceFileGraphInput,
)
from src.graph.repository import (
    GraphEdgeInput,
    GraphEvidenceInput,
    GraphMetricInput,
    GraphNodeInput,
    GraphRepository,
    GraphSnapshot,
)


class FakeSourceFileReader:
    def __init__(self, files: list[SourceFileGraphInput]) -> None:
        self.files = files

    async def list_for_graph(self, repository_version_id: UUID) -> list[SourceFileGraphInput]:
        return self.files


class FakeGraphRepository:
    def __init__(self) -> None:
        self.nodes: dict[tuple[UUID, str], SimpleNamespace] = {}
        self.edges: dict[tuple[UUID, UUID, UUID, str], SimpleNamespace] = {}
        self.evidence: dict[tuple[UUID, str], SimpleNamespace] = {}

    async def upsert_node(self, node: GraphNodeInput) -> SimpleNamespace:
        key = (node.repository_id, node.canonical_key)
        persisted = SimpleNamespace(
            id=self.nodes.get(key, SimpleNamespace(id=uuid4())).id,
            **asdict(node),
        )
        self.nodes[key] = persisted
        return persisted

    async def upsert_edge(self, edge: GraphEdgeInput) -> SimpleNamespace:
        key = (
            edge.repository_id,
            edge.source_node_id,
            edge.target_node_id,
            edge.relationship_type,
        )
        persisted = SimpleNamespace(
            id=self.edges.get(key, SimpleNamespace(id=uuid4())).id,
            **asdict(edge),
        )
        self.edges[key] = persisted
        return persisted

    async def upsert_evidence(self, evidence: GraphEvidenceInput) -> SimpleNamespace:
        key = (evidence.repository_id, evidence.canonical_key)
        persisted = SimpleNamespace(
            id=self.evidence.get(key, SimpleNamespace(id=uuid4())).id,
            **asdict(evidence),
        )
        self.evidence[key] = persisted
        return persisted

    async def upsert_metric(self, metric: GraphMetricInput) -> SimpleNamespace:
        raise NotImplementedError

    async def neighbors(self, node_id: UUID, *, limit: int = 100) -> GraphSnapshot:
        raise NotImplementedError

    async def subgraph(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        limit: int = 500,
    ) -> GraphSnapshot:
        raise NotImplementedError


def source_file(path: str, *, language: str | None = "Python") -> SourceFileGraphInput:
    return SourceFileGraphInput(
        id=uuid4(),
        path=path,
        file_kind="source",
        language=language,
        blob_sha="a" * 40,
        size=42,
    )


@pytest.mark.asyncio
async def test_builds_idempotent_evidence_backed_filesystem_graph() -> None:
    repository_id = uuid4()
    repository_version_id = uuid4()
    graph_repository = FakeGraphRepository()
    builder = FilesystemGraphBuilder(
        graph_repository=cast(GraphRepository, graph_repository),
        source_file_reader=FakeSourceFileReader(
            [
                source_file("src/pkg/service.py"),
                source_file("README.md", language="Markdown"),
                source_file("src/main.py"),
            ]
        ),
    )

    first = await builder.build(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
    )
    second = await builder.build(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
    )

    assert first == second
    assert first.nodes == 6
    assert first.directories == 2
    assert first.files == 3
    assert first.edges == 5
    assert first.evidence == 5
    assert len(graph_repository.nodes) == 6
    assert len(graph_repository.edges) == 5
    assert len(graph_repository.evidence) == 5
    assert {edge.relationship_type for edge in graph_repository.edges.values()} == {CONTAINS}
    assert all(edge.provenance for edge in graph_repository.edges.values())
    assert {evidence.target_edge_id for evidence in graph_repository.evidence.values()} == {
        edge.id for edge in graph_repository.edges.values()
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["../secret.py", "/absolute.py"])
async def test_rejects_path_that_can_escape_snapshot_root(path: str) -> None:
    builder = FilesystemGraphBuilder(
        graph_repository=cast(GraphRepository, FakeGraphRepository()),
        source_file_reader=FakeSourceFileReader([source_file(path)]),
    )

    with pytest.raises(ValueError, match="Invalid repository file path"):
        await builder.build(repository_id=uuid4(), repository_version_id=uuid4())
