from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.graph.canonical import evidence_key
from src.graph.models import (
    EntityType,
    EvidenceType,
    GraphEdge,
    GraphNode,
    KnowledgeKind,
    RelationshipType,
)
from src.graph.repository import (
    GraphEdgeInput,
    GraphEvidenceInput,
    GraphRepository,
)

SUBSYSTEM_GRAPH_VERSION = "subsystem-graph-v1"
MAX_SUBSYSTEM_GRAPH_IMPORTS = 100_000
MAX_SUBSYSTEM_DEPENDENCIES = 10_000
MAX_DEPENDENCY_EVIDENCE = 100


@dataclass(frozen=True, slots=True)
class SubsystemGraphNodeInput:
    node_id: UUID
    canonical_key: str
    name: str
    status: str
    confidence: float


@dataclass(frozen=True, slots=True)
class SubsystemMembershipInput:
    file_node_id: UUID
    subsystem_node_id: UUID


@dataclass(frozen=True, slots=True)
class FileImportInput:
    edge_id: UUID
    source_file_node_id: UUID
    target_file_node_id: UUID
    source_path: str
    target_path: str


@dataclass(frozen=True, slots=True)
class SubsystemGraphInput:
    subsystems: tuple[SubsystemGraphNodeInput, ...]
    memberships: tuple[SubsystemMembershipInput, ...]
    imports: tuple[FileImportInput, ...]


@dataclass(frozen=True, slots=True)
class SubsystemDependency:
    source: SubsystemGraphNodeInput
    target: SubsystemGraphNodeInput
    imports: tuple[FileImportInput, ...]


@dataclass(frozen=True, slots=True)
class SubsystemGraphSummary:
    subsystems: int
    file_imports: int
    dependencies: int
    evidence: int
    stale_dependencies: int
    algorithm_version: str = SUBSYSTEM_GRAPH_VERSION


class SubsystemGraphReader(Protocol):
    async def read(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> SubsystemGraphInput: ...


class SubsystemGraphStore(Protocol):
    async def prune_dependencies(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        retained_pairs: Sequence[tuple[UUID, UUID]],
    ) -> int: ...


class PostgresSubsystemGraphStore:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def read(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> SubsystemGraphInput:
        node_rows = await self.session.execute(
            select(GraphNode).where(
                GraphNode.repository_id == repository_id,
                GraphNode.repository_version_id == repository_version_id,
                GraphNode.entity_type.in_((EntityType.FILE, EntityType.SUBSYSTEM)),
            )
        )
        nodes = list(node_rows.scalars().all())
        nodes_by_id = {node.id: node for node in nodes}
        subsystems = tuple(
            SubsystemGraphNodeInput(
                node_id=node.id,
                canonical_key=node.canonical_key,
                name=node.name,
                status=(
                    status
                    if isinstance((status := node.details.get("status")), str)
                    else "candidate"
                ),
                confidence=node.confidence,
            )
            for node in sorted(nodes, key=lambda item: item.canonical_key)
            if node.entity_type == EntityType.SUBSYSTEM
        )
        subsystem_ids = {item.node_id for item in subsystems}
        file_nodes = {
            node.id: node
            for node in nodes
            if node.entity_type == EntityType.FILE and isinstance(node.details.get("path"), str)
        }
        if not subsystem_ids or not file_nodes:
            return SubsystemGraphInput(subsystems=subsystems, memberships=(), imports=())

        membership_rows = await self.session.execute(
            select(GraphEdge).where(
                GraphEdge.repository_id == repository_id,
                GraphEdge.repository_version_id == repository_version_id,
                GraphEdge.relationship_type == RelationshipType.PART_OF_SUBSYSTEM,
                GraphEdge.source_node_id.in_(file_nodes),
                GraphEdge.target_node_id.in_(subsystem_ids),
            )
        )
        memberships = tuple(
            SubsystemMembershipInput(
                file_node_id=edge.source_node_id,
                subsystem_node_id=edge.target_node_id,
            )
            for edge in membership_rows.scalars().all()
        )
        member_file_ids = {membership.file_node_id for membership in memberships}
        if not member_file_ids:
            return SubsystemGraphInput(subsystems=subsystems, memberships=memberships, imports=())
        import_rows = await self.session.execute(
            select(GraphEdge)
            .where(
                GraphEdge.repository_id == repository_id,
                GraphEdge.repository_version_id == repository_version_id,
                GraphEdge.relationship_type == RelationshipType.IMPORTS,
                GraphEdge.knowledge_kind == KnowledgeKind.DETERMINISTIC,
                GraphEdge.source_node_id.in_(member_file_ids),
                GraphEdge.target_node_id.in_(member_file_ids),
            )
            .limit(MAX_SUBSYSTEM_GRAPH_IMPORTS + 1)
        )
        import_edges = list(import_rows.scalars().all())
        if len(import_edges) > MAX_SUBSYSTEM_GRAPH_IMPORTS:
            raise ValueError(
                "Subsystem graph import limit exceeded: "
                f"{len(import_edges)} > {MAX_SUBSYSTEM_GRAPH_IMPORTS}"
            )
        imports = tuple(
            FileImportInput(
                edge_id=edge.id,
                source_file_node_id=edge.source_node_id,
                target_file_node_id=edge.target_node_id,
                source_path=str(nodes_by_id[edge.source_node_id].details["path"]),
                target_path=str(nodes_by_id[edge.target_node_id].details["path"]),
            )
            for edge in import_edges
        )
        return SubsystemGraphInput(
            subsystems=subsystems,
            memberships=memberships,
            imports=imports,
        )

    async def prune_dependencies(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        retained_pairs: Sequence[tuple[UUID, UUID]],
    ) -> int:
        subsystem_ids = select(GraphNode.id).where(
            GraphNode.repository_id == repository_id,
            GraphNode.repository_version_id == repository_version_id,
            GraphNode.entity_type == EntityType.SUBSYSTEM,
        )
        existing_rows = await self.session.execute(
            select(GraphEdge.id, GraphEdge.source_node_id, GraphEdge.target_node_id).where(
                GraphEdge.repository_id == repository_id,
                GraphEdge.repository_version_id == repository_version_id,
                GraphEdge.relationship_type == RelationshipType.DEPENDS_ON,
                GraphEdge.source_node_id.in_(subsystem_ids),
                GraphEdge.provenance["algorithm"].as_string() == SUBSYSTEM_GRAPH_VERSION,
            )
        )
        retained = set(retained_pairs)
        stale_ids = [
            edge_id
            for edge_id, source_id, target_id in existing_rows.all()
            if (source_id, target_id) not in retained
        ]
        if not stale_ids:
            return 0
        result = await self.session.execute(delete(GraphEdge).where(GraphEdge.id.in_(stale_ids)))
        return int(getattr(result, "rowcount", 0) or 0)


class DeterministicSubsystemGraphAnalyzer:
    def analyze(self, data: SubsystemGraphInput) -> tuple[SubsystemDependency, ...]:
        subsystems = {subsystem.node_id: subsystem for subsystem in data.subsystems}
        subsystem_by_file = {
            membership.file_node_id: membership.subsystem_node_id for membership in data.memberships
        }
        imports_by_pair: dict[tuple[UUID, UUID], list[FileImportInput]] = defaultdict(list)
        for item in data.imports:
            source_subsystem = subsystem_by_file.get(item.source_file_node_id)
            target_subsystem = subsystem_by_file.get(item.target_file_node_id)
            if (
                source_subsystem is None
                or target_subsystem is None
                or source_subsystem == target_subsystem
            ):
                continue
            imports_by_pair[(source_subsystem, target_subsystem)].append(item)
        if len(imports_by_pair) > MAX_SUBSYSTEM_DEPENDENCIES:
            raise ValueError(
                "Subsystem dependency limit exceeded: "
                f"{len(imports_by_pair)} > {MAX_SUBSYSTEM_DEPENDENCIES}"
            )
        return tuple(
            SubsystemDependency(
                source=subsystems[source_id],
                target=subsystems[target_id],
                imports=tuple(sorted(imports, key=lambda item: str(item.edge_id))),
            )
            for (source_id, target_id), imports in sorted(
                imports_by_pair.items(),
                key=lambda item: (
                    subsystems[item[0][0]].canonical_key,
                    subsystems[item[0][1]].canonical_key,
                ),
            )
        )


class SubsystemGraphBuilder:
    def __init__(
        self,
        *,
        graph_repository: GraphRepository,
        reader: SubsystemGraphReader,
        store: SubsystemGraphStore,
        analyzer: DeterministicSubsystemGraphAnalyzer | None = None,
    ) -> None:
        self.graph_repository = graph_repository
        self.reader = reader
        self.store = store
        self.analyzer = analyzer or DeterministicSubsystemGraphAnalyzer()

    async def build(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> SubsystemGraphSummary:
        data = await self.reader.read(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
        )
        dependencies = self.analyzer.analyze(data)
        provenance: dict[str, object] = {
            "component": "subsystem_graph",
            "algorithm": SUBSYSTEM_GRAPH_VERSION,
            "kind": "derived_from_file_imports",
        }
        evidence_count = 0
        retained_pairs: list[tuple[UUID, UUID]] = []
        for dependency in dependencies:
            confidence = min(dependency.source.confidence, dependency.target.confidence)
            edge = await self.graph_repository.upsert_edge(
                GraphEdgeInput(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    source_node_id=dependency.source.node_id,
                    target_node_id=dependency.target.node_id,
                    relationship_type=RelationshipType.DEPENDS_ON,
                    knowledge_kind=KnowledgeKind.DERIVED,
                    confidence=confidence,
                    provenance=provenance,
                    metadata={
                        "source_status": dependency.source.status,
                        "target_status": dependency.target.status,
                        "import_count": len(dependency.imports),
                        "import_edge_ids": [str(item.edge_id) for item in dependency.imports],
                    },
                )
            )
            retained_pairs.append((dependency.source.node_id, dependency.target.node_id))
            for item in dependency.imports[:MAX_DEPENDENCY_EVIDENCE]:
                await self.graph_repository.upsert_evidence(
                    GraphEvidenceInput(
                        repository_id=repository_id,
                        repository_version_id=repository_version_id,
                        canonical_key=evidence_key(
                            repository_id,
                            repository_version_id,
                            dependency.source.canonical_key,
                            dependency.target.canonical_key,
                            item.edge_id,
                            SUBSYSTEM_GRAPH_VERSION,
                        ),
                        source_node_id=item.source_file_node_id,
                        target_edge_id=edge.id,
                        evidence_type=EvidenceType.GRAPH_PATH,
                        relationship=RelationshipType.DEPENDS_ON,
                        excerpt=f"{item.source_path} imports {item.target_path}",
                        confidence=confidence,
                        provenance=provenance,
                        metadata={"import_edge_id": str(item.edge_id)},
                    )
                )
                evidence_count += 1
        stale_dependencies = await self.store.prune_dependencies(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            retained_pairs=retained_pairs,
        )
        return SubsystemGraphSummary(
            subsystems=len(data.subsystems),
            file_imports=len(data.imports),
            dependencies=len(dependencies),
            evidence=evidence_count,
            stale_dependencies=stale_dependencies,
        )
