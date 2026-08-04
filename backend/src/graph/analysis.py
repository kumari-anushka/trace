from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol, cast
from uuid import UUID

import networkx as nx

from src.graph.models import EntityType, GraphEdge, GraphNode, RelationshipType
from src.graph.repository import GraphMetricInput, GraphSnapshot

ANALYSIS_IMPLEMENTATION_VERSION = "1.0.0"


class GraphAnalysisRepository(Protocol):
    async def load_for_analysis(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        max_nodes: int = ...,
        max_edges: int = ...,
    ) -> GraphSnapshot: ...

    async def replace_metrics(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        algorithm_version: str,
        metrics: Sequence[GraphMetricInput],
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class GraphAnalysisSummary:
    nodes: int
    edges: int
    metrics: int
    connected_components: int
    communities: int
    bridges: int
    dependency_cycles: int


@dataclass(frozen=True, slots=True)
class GraphAnalysisResult:
    summary: GraphAnalysisSummary
    metrics: tuple[GraphMetricInput, ...]


class NetworkXGraphAnalyzer:
    """Compute reproducible derived metrics over deterministic graph projections."""

    def __init__(self) -> None:
        self.algorithm_version = (
            f"networkx-{nx.__version__}:trace-{ANALYSIS_IMPLEMENTATION_VERSION}"
        )

    def analyze(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        snapshot: GraphSnapshot,
    ) -> GraphAnalysisResult:
        nodes = sorted(snapshot.nodes, key=lambda node: node.canonical_key)
        edges = sorted(
            snapshot.edges,
            key=lambda edge: (edge.relationship_type, str(edge.id)),
        )
        nodes_by_id = {node.id: node for node in nodes}
        topology = self._topology(nodes, edges)
        dependency_graph = self._dependency_graph(nodes, edges)

        components = _ordered_groups(nx.connected_components(topology), nodes_by_id)
        communities = self._communities(dependency_graph, nodes_by_id)
        bridges = sorted(
            cast(Iterable[tuple[UUID, UUID]], nx.bridges(topology)),
            key=lambda pair: _pair_keys(pair, nodes_by_id),
        )
        dependency_cycles = _ordered_groups(
            (
                component
                for component in nx.strongly_connected_components(dependency_graph)
                if len(component) > 1
            ),
            nodes_by_id,
        )

        metrics: list[GraphMetricInput] = []

        def add_metric(
            metric_name: str,
            scope_key: str,
            value: float,
            *,
            node_id: UUID | None = None,
            metadata: dict[str, object] | None = None,
        ) -> None:
            metrics.append(
                GraphMetricInput(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    node_id=node_id,
                    metric_name=metric_name,
                    scope_key=scope_key,
                    value=value,
                    algorithm_version=self.algorithm_version,
                    metadata={
                        "implementation_version": ANALYSIS_IMPLEMENTATION_VERSION,
                        "networkx_version": nx.__version__,
                        **(metadata or {}),
                    },
                )
            )

        global_metrics = {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "connected_component_count": len(components),
            "community_count": len(communities),
            "bridge_count": len(bridges),
            "dependency_cycle_count": len(dependency_cycles),
        }
        for metric_name, value in global_metrics.items():
            add_metric(metric_name, "graph", float(value), metadata={"projection": "summary"})

        for node_id, centrality in sorted(
            nx.degree_centrality(topology).items(),
            key=lambda item: nodes_by_id[item[0]].canonical_key,
        ):
            node = nodes_by_id[node_id]
            add_metric(
                "degree_centrality",
                node.canonical_key,
                centrality,
                node_id=node_id,
                metadata={
                    "projection": "full_undirected_graph",
                    "entity_type": node.entity_type,
                },
            )

        for index, component in enumerate(components):
            component_key = _group_key("component", component, nodes_by_id)
            for node_id in component:
                add_metric(
                    "connected_component_membership",
                    nodes_by_id[node_id].canonical_key,
                    float(len(component)),
                    node_id=node_id,
                    metadata={
                        "projection": "full_undirected_graph",
                        "component_index": index,
                        "component_key": component_key,
                    },
                )

        for index, community in enumerate(communities):
            community_key = _group_key("community", community, nodes_by_id)
            for node_id in community:
                add_metric(
                    "community_membership",
                    nodes_by_id[node_id].canonical_key,
                    float(len(community)),
                    node_id=node_id,
                    metadata={
                        "projection": "internal_file_imports",
                        "community_index": index,
                        "community_key": community_key,
                    },
                )

        edges_by_pair: dict[frozenset[UUID], list[GraphEdge]] = {}
        for edge in edges:
            edges_by_pair.setdefault(
                frozenset((edge.source_node_id, edge.target_node_id)), []
            ).append(edge)
        for source_id, target_id in bridges:
            source_key, target_key = _pair_keys((source_id, target_id), nodes_by_id)
            bridge_edges = edges_by_pair[frozenset((source_id, target_id))]
            add_metric(
                "bridge",
                _digest_key("bridge", (source_key, target_key)),
                1.0,
                metadata={
                    "projection": "full_undirected_graph",
                    "source_node_id": str(source_id),
                    "target_node_id": str(target_id),
                    "source_key": source_key,
                    "target_key": target_key,
                    "edge_ids": [str(edge.id) for edge in bridge_edges],
                    "relationships": sorted({edge.relationship_type for edge in bridge_edges}),
                },
            )

        for component in dependency_cycles:
            component_graph = dependency_graph.subgraph(component)
            cycle_edges = list(nx.find_cycle(component_graph))
            canonical_keys = tuple(nodes_by_id[node_id].canonical_key for node_id in component)
            add_metric(
                "dependency_cycle",
                _digest_key("dependency-cycle", canonical_keys),
                float(len(component)),
                metadata={
                    "projection": "internal_file_imports",
                    "node_ids": [str(node_id) for node_id in component],
                    "canonical_keys": list(canonical_keys),
                    "representative_cycle": [
                        {
                            "source_node_id": str(source_id),
                            "target_node_id": str(target_id),
                            "source_key": nodes_by_id[source_id].canonical_key,
                            "target_key": nodes_by_id[target_id].canonical_key,
                        }
                        for source_id, target_id in cycle_edges
                    ],
                },
            )

        return GraphAnalysisResult(
            summary=GraphAnalysisSummary(
                nodes=len(nodes),
                edges=len(edges),
                metrics=len(metrics),
                connected_components=len(components),
                communities=len(communities),
                bridges=len(bridges),
                dependency_cycles=len(dependency_cycles),
            ),
            metrics=tuple(metrics),
        )

    @staticmethod
    def _topology(nodes: Sequence[GraphNode], edges: Sequence[GraphEdge]) -> nx.Graph[UUID]:
        graph: nx.Graph[UUID] = nx.Graph()
        graph.add_nodes_from(node.id for node in nodes)
        graph.add_edges_from((edge.source_node_id, edge.target_node_id) for edge in edges)
        return graph

    @staticmethod
    def _dependency_graph(
        nodes: Sequence[GraphNode], edges: Sequence[GraphEdge]
    ) -> nx.DiGraph[UUID]:
        file_ids = {node.id for node in nodes if node.entity_type == EntityType.FILE}
        graph: nx.DiGraph[UUID] = nx.DiGraph()
        graph.add_nodes_from(file_ids)
        graph.add_edges_from(
            (edge.source_node_id, edge.target_node_id)
            for edge in edges
            if edge.relationship_type == RelationshipType.IMPORTS
            and edge.source_node_id in file_ids
            and edge.target_node_id in file_ids
        )
        return graph

    @staticmethod
    def _communities(
        dependency_graph: nx.DiGraph[UUID],
        nodes_by_id: dict[UUID, GraphNode],
    ) -> tuple[tuple[UUID, ...], ...]:
        undirected = dependency_graph.to_undirected()
        if undirected.number_of_edges() == 0:
            groups: Iterable[Iterable[UUID]] = ({node_id} for node_id in undirected.nodes)
        else:
            groups = cast(
                Iterable[Iterable[UUID]],
                nx.community.louvain_communities(undirected, seed=0),
            )
        return _ordered_groups(groups, nodes_by_id)


class GraphAnalysisBuilder:
    def __init__(
        self,
        *,
        repository: GraphAnalysisRepository,
        analyzer: NetworkXGraphAnalyzer | None = None,
    ) -> None:
        self.repository = repository
        self.analyzer = analyzer or NetworkXGraphAnalyzer()

    async def build(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
    ) -> GraphAnalysisSummary:
        snapshot = await self.repository.load_for_analysis(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
        )
        result = self.analyzer.analyze(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            snapshot=snapshot,
        )
        await self.repository.replace_metrics(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            algorithm_version=self.analyzer.algorithm_version,
            metrics=result.metrics,
        )
        return result.summary


def _ordered_groups(
    groups: Iterable[Iterable[UUID]],
    nodes_by_id: dict[UUID, GraphNode],
) -> tuple[tuple[UUID, ...], ...]:
    ordered = [
        tuple(sorted(group, key=lambda node_id: nodes_by_id[node_id].canonical_key))
        for group in groups
    ]
    return tuple(
        sorted(
            ordered,
            key=lambda group: tuple(nodes_by_id[node_id].canonical_key for node_id in group),
        )
    )


def _pair_keys(pair: tuple[UUID, UUID], nodes_by_id: dict[UUID, GraphNode]) -> tuple[str, str]:
    keys = sorted(nodes_by_id[node_id].canonical_key for node_id in pair)
    return keys[0], keys[1]


def _group_key(
    prefix: str,
    group: tuple[UUID, ...],
    nodes_by_id: dict[UUID, GraphNode],
) -> str:
    return _digest_key(prefix, tuple(nodes_by_id[node_id].canonical_key for node_id in group))


def _digest_key(prefix: str, parts: tuple[str, ...]) -> str:
    digest = sha256("\0".join(parts).encode()).hexdigest()
    return f"{prefix}:{digest}"
