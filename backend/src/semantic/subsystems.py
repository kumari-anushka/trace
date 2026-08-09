from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations
from math import sqrt
from pathlib import PurePosixPath
from typing import Protocol, cast
from uuid import UUID

import networkx as nx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.graph.canonical import evidence_key, subsystem_key
from src.graph.models import (
    EntityType,
    EvidenceType,
    GraphEdge,
    GraphMetric,
    GraphNode,
    KnowledgeKind,
    RelationshipType,
)
from src.graph.repository import (
    GraphEdgeInput,
    GraphEvidenceInput,
    GraphNodeInput,
    GraphRepository,
)
from src.semantic.models import Document, DocumentSourceType, Embedding, EmbeddingSpace

SUBSYSTEM_DISCOVERY_VERSION = "subsystem-discovery-v1"
MAX_SUBSYSTEM_FILES = 10_000
MAX_SIGNAL_BUCKET_SIZE = 250
MAX_CANDIDATE_PAIRS = 200_000
EMBEDDING_SIMILARITY_THRESHOLD = 0.55
_NAME_TOKEN_PATTERN = re.compile(r"[a-z][a-z0-9]+")
_GENERIC_NAME_TOKENS = frozenset(
    {
        "app",
        "base",
        "common",
        "core",
        "index",
        "init",
        "main",
        "module",
        "src",
        "test",
        "tests",
        "types",
        "utils",
    }
)


@dataclass(frozen=True, slots=True)
class SubsystemFileInput:
    node_id: UUID
    canonical_key: str
    path: str
    community_key: str | None = None
    embedding: tuple[float, ...] | None = None


@dataclass(frozen=True, slots=True)
class CochangeInput:
    left_node_id: UUID
    right_node_id: UUID
    count: int


@dataclass(frozen=True, slots=True)
class SubsystemDiscoveryInput:
    files: tuple[SubsystemFileInput, ...]
    cochanges: tuple[CochangeInput, ...] = ()


@dataclass(frozen=True, slots=True)
class SubsystemCandidate:
    canonical_key: str
    name: str
    description: str
    confidence: float
    members: tuple[SubsystemFileInput, ...]
    signals: tuple[str, ...]
    signal_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class SubsystemDiscoverySummary:
    files: int
    candidates: int
    memberships: int
    evidence: int
    stale_candidates: int
    algorithm_version: str = SUBSYSTEM_DISCOVERY_VERSION


class SubsystemSignalReader(Protocol):
    async def read(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> SubsystemDiscoveryInput: ...


class SubsystemCandidateStore(Protocol):
    async def prune_candidates(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        retained_canonical_keys: Sequence[str],
    ) -> int: ...


class PostgresSubsystemDiscoveryStore:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def read(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> SubsystemDiscoveryInput:
        node_rows = await self.session.execute(
            select(GraphNode)
            .where(
                GraphNode.repository_id == repository_id,
                GraphNode.repository_version_id == repository_version_id,
                GraphNode.entity_type == EntityType.FILE,
                GraphNode.knowledge_kind == KnowledgeKind.DETERMINISTIC,
            )
            .order_by(GraphNode.canonical_key)
        )
        file_nodes = [
            node
            for node in node_rows.scalars().all()
            if node.details.get("file_kind") in {"source", "test"}
            and isinstance(node.details.get("path"), str)
        ]
        if len(file_nodes) > MAX_SUBSYSTEM_FILES:
            raise ValueError(
                f"Subsystem file limit exceeded: {len(file_nodes)} > {MAX_SUBSYSTEM_FILES}"
            )
        node_ids = [node.id for node in file_nodes]
        communities: dict[UUID, str] = {}
        embeddings: dict[UUID, tuple[float, ...]] = {}
        cochanges: list[CochangeInput] = []

        if node_ids:
            metric_rows = await self.session.execute(
                select(GraphMetric).where(
                    GraphMetric.repository_id == repository_id,
                    GraphMetric.repository_version_id == repository_version_id,
                    GraphMetric.node_id.in_(node_ids),
                    GraphMetric.metric_name == "community_membership",
                )
            )
            for metric in metric_rows.scalars().all():
                community_key = metric.details.get("community_key")
                if metric.node_id is not None and isinstance(community_key, str):
                    communities[metric.node_id] = community_key

            embedding_rows = await self.session.execute(
                select(Document.source_node_id, Embedding.vector)
                .join(Embedding, Embedding.document_id == Document.id)
                .join(EmbeddingSpace, EmbeddingSpace.id == Embedding.embedding_space_id)
                .where(
                    Document.repository_id == repository_id,
                    Document.repository_version_id == repository_version_id,
                    Document.source_type == DocumentSourceType.SOURCE_SUMMARY,
                    Document.source_node_id.in_(node_ids),
                    EmbeddingSpace.is_active.is_(True),
                    Embedding.content_hash == Document.content_hash,
                )
            )
            vectors_by_node: dict[UUID, list[Sequence[float]]] = defaultdict(list)
            for node_id, vector in embedding_rows.all():
                if node_id is not None:
                    vectors_by_node[node_id].append(cast(Sequence[float], vector))
            embeddings = {
                node_id: _average_vectors(vectors) for node_id, vectors in vectors_by_node.items()
            }

            modification_rows = await self.session.execute(
                select(GraphEdge.source_node_id, GraphEdge.target_node_id).where(
                    GraphEdge.repository_id == repository_id,
                    GraphEdge.repository_version_id == repository_version_id,
                    GraphEdge.relationship_type == RelationshipType.MODIFIES,
                    GraphEdge.target_node_id.in_(node_ids),
                    GraphEdge.knowledge_kind == KnowledgeKind.DETERMINISTIC,
                )
            )
            files_by_artifact: dict[UUID, set[UUID]] = defaultdict(set)
            for artifact_node_id, file_node_id in modification_rows.all():
                files_by_artifact[artifact_node_id].add(file_node_id)
            pair_counts: Counter[tuple[UUID, UUID]] = Counter()
            for modified_file_ids in files_by_artifact.values():
                ordered_ids = sorted(modified_file_ids, key=str)
                pair_counts.update(combinations(ordered_ids, 2))
            cochanges = [
                CochangeInput(left_node_id=left, right_node_id=right, count=count)
                for (left, right), count in sorted(
                    pair_counts.items(), key=lambda item: (str(item[0][0]), str(item[0][1]))
                )
            ]

        return SubsystemDiscoveryInput(
            files=tuple(
                SubsystemFileInput(
                    node_id=node.id,
                    canonical_key=node.canonical_key,
                    path=cast(str, node.details["path"]),
                    community_key=communities.get(node.id),
                    embedding=embeddings.get(node.id),
                )
                for node in file_nodes
            ),
            cochanges=tuple(cochanges),
        )

    async def prune_candidates(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        retained_canonical_keys: Sequence[str],
    ) -> int:
        statement = delete(GraphNode).where(
            GraphNode.repository_id == repository_id,
            GraphNode.repository_version_id == repository_version_id,
            GraphNode.entity_type == EntityType.SUBSYSTEM,
            GraphNode.provenance["algorithm"].as_string() == SUBSYSTEM_DISCOVERY_VERSION,
        )
        if retained_canonical_keys:
            statement = statement.where(GraphNode.canonical_key.not_in(retained_canonical_keys))
        result = await self.session.execute(statement)
        return int(getattr(result, "rowcount", 0) or 0)


class DeterministicSubsystemDiscoverer:
    def discover(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        data: SubsystemDiscoveryInput,
    ) -> tuple[SubsystemCandidate, ...]:
        files = tuple(sorted(data.files, key=lambda item: item.canonical_key))
        files_by_id = {file.node_id: file for file in files}
        candidate_pairs: set[tuple[UUID, UUID]] = set()

        directory_buckets: dict[str, list[UUID]] = defaultdict(list)
        community_buckets: dict[str, list[UUID]] = defaultdict(list)
        naming_buckets: dict[str, list[UUID]] = defaultdict(list)
        for file in files:
            directory_buckets[_directory_key(file.path)].append(file.node_id)
            if file.community_key:
                community_buckets[file.community_key].append(file.node_id)
            for token in _name_tokens(file.path):
                naming_buckets[token].append(file.node_id)

        for buckets in (directory_buckets, community_buckets, naming_buckets):
            for member_ids in buckets.values():
                _add_bucket_pairs(candidate_pairs, member_ids)
        cochange_counts = {
            _pair_key(item.left_node_id, item.right_node_id): item.count
            for item in data.cochanges
            if item.left_node_id in files_by_id and item.right_node_id in files_by_id
        }
        candidate_pairs.update(cochange_counts)
        if len(candidate_pairs) > MAX_CANDIDATE_PAIRS:
            raise ValueError(
                f"Subsystem candidate pair limit exceeded: "
                f"{len(candidate_pairs)} > {MAX_CANDIDATE_PAIRS}"
            )

        similarity_graph: nx.Graph[UUID] = nx.Graph()
        pair_signals: dict[tuple[UUID, UUID], tuple[str, ...]] = {}
        for left_id, right_id in sorted(
            candidate_pairs, key=lambda pair: (str(pair[0]), str(pair[1]))
        ):
            left = files_by_id[left_id]
            right = files_by_id[right_id]
            signals = _signals(left, right, cochange_counts.get((left_id, right_id), 0))
            if len(signals) < 2:
                continue
            similarity_graph.add_edge(left_id, right_id)
            pair_signals[(left_id, right_id)] = signals

        candidates: list[SubsystemCandidate] = []
        components = sorted(
            nx.connected_components(similarity_graph),
            key=lambda component: tuple(
                files_by_id[node_id].canonical_key
                for node_id in sorted(component, key=lambda item: files_by_id[item].canonical_key)
            ),
        )
        for component in components:
            members = tuple(
                sorted((files_by_id[node_id] for node_id in component), key=lambda item: item.path)
            )
            internal_signals = Counter[str]()
            qualifying_edges = 0
            for left_id, right_id in combinations(
                sorted(component, key=lambda node_id: files_by_id[node_id].canonical_key), 2
            ):
                edge_signals = pair_signals.get(_pair_key(left_id, right_id))
                if edge_signals:
                    qualifying_edges += 1
                    internal_signals.update(edge_signals)
            signals = tuple(sorted(internal_signals))
            canonical_key = subsystem_key(
                repository_id,
                repository_version_id,
                tuple(sorted(member.canonical_key for member in members)),
            )
            confidence = _confidence(
                member_count=len(members),
                qualifying_edges=qualifying_edges,
                distinct_signals=len(signals),
            )
            name = _candidate_name(members, canonical_key)
            candidates.append(
                SubsystemCandidate(
                    canonical_key=canonical_key,
                    name=name,
                    description=(
                        f"Candidate cluster of {len(members)} files supported by "
                        f"{', '.join(signals)}."
                    ),
                    confidence=confidence,
                    members=members,
                    signals=signals,
                    signal_counts=tuple(sorted(internal_signals.items())),
                )
            )
        return tuple(candidates)


class SubsystemDiscoveryBuilder:
    def __init__(
        self,
        *,
        graph_repository: GraphRepository,
        signal_reader: SubsystemSignalReader,
        candidate_store: SubsystemCandidateStore,
        discoverer: DeterministicSubsystemDiscoverer | None = None,
    ) -> None:
        self.graph_repository = graph_repository
        self.signal_reader = signal_reader
        self.candidate_store = candidate_store
        self.discoverer = discoverer or DeterministicSubsystemDiscoverer()

    async def build(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
    ) -> SubsystemDiscoverySummary:
        data = await self.signal_reader.read(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
        )
        candidates = self.discoverer.discover(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            data=data,
        )
        provenance: dict[str, object] = {
            "component": "subsystem_discovery",
            "algorithm": SUBSYSTEM_DISCOVERY_VERSION,
            "kind": "deterministic_candidate_generation",
        }
        membership_count = 0
        evidence_count = 0
        for candidate in candidates:
            subsystem_node = await self.graph_repository.upsert_node(
                GraphNodeInput(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    entity_type=EntityType.SUBSYSTEM,
                    canonical_key=candidate.canonical_key,
                    name=candidate.name,
                    description=candidate.description,
                    knowledge_kind=KnowledgeKind.INFERRED,
                    confidence=candidate.confidence,
                    provenance=provenance,
                    metadata={
                        "status": "candidate",
                        "member_count": len(candidate.members),
                        "member_paths": [member.path for member in candidate.members],
                        "signals": list(candidate.signals),
                        "signal_counts": dict(candidate.signal_counts),
                    },
                )
            )
            for member in candidate.members:
                edge = await self.graph_repository.upsert_edge(
                    GraphEdgeInput(
                        repository_id=repository_id,
                        repository_version_id=repository_version_id,
                        source_node_id=member.node_id,
                        target_node_id=subsystem_node.id,
                        relationship_type=RelationshipType.PART_OF_SUBSYSTEM,
                        knowledge_kind=KnowledgeKind.INFERRED,
                        confidence=candidate.confidence,
                        provenance=provenance,
                        metadata={"status": "candidate", "signals": list(candidate.signals)},
                    )
                )
                membership_count += 1
                await self.graph_repository.upsert_evidence(
                    GraphEvidenceInput(
                        repository_id=repository_id,
                        repository_version_id=repository_version_id,
                        canonical_key=evidence_key(
                            repository_id,
                            repository_version_id,
                            candidate.canonical_key,
                            member.canonical_key,
                            SUBSYSTEM_DISCOVERY_VERSION,
                        ),
                        source_node_id=member.node_id,
                        target_node_id=subsystem_node.id,
                        evidence_type=EvidenceType.METRIC,
                        relationship=RelationshipType.PART_OF_SUBSYSTEM,
                        excerpt=(f"{member.path} grouped by {', '.join(candidate.signals)}"),
                        confidence=candidate.confidence,
                        provenance=provenance,
                        metadata={
                            "membership_edge_id": str(edge.id),
                            "signals": list(candidate.signals),
                            "signal_counts": dict(candidate.signal_counts),
                        },
                    )
                )
                evidence_count += 1

        stale_candidates = await self.candidate_store.prune_candidates(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            retained_canonical_keys=[candidate.canonical_key for candidate in candidates],
        )
        return SubsystemDiscoverySummary(
            files=len(data.files),
            candidates=len(candidates),
            memberships=membership_count,
            evidence=evidence_count,
            stale_candidates=stale_candidates,
        )


def _add_bucket_pairs(pairs: set[tuple[UUID, UUID]], member_ids: Sequence[UUID]) -> None:
    unique_ids = sorted(set(member_ids), key=str)
    if len(unique_ids) < 2:
        return
    if len(unique_ids) > MAX_SIGNAL_BUCKET_SIZE:
        return
    pairs.update(_pair_key(left, right) for left, right in combinations(unique_ids, 2))


def _pair_key(left: UUID, right: UUID) -> tuple[UUID, UUID]:
    return (left, right) if str(left) < str(right) else (right, left)


def _signals(
    left: SubsystemFileInput, right: SubsystemFileInput, cochange_count: int
) -> tuple[str, ...]:
    signals: list[str] = []
    if _directory_key(left.path) == _directory_key(right.path):
        signals.append("directory")
    if left.community_key and left.community_key == right.community_key:
        signals.append("graph_community")
    if _name_tokens(left.path) & _name_tokens(right.path):
        signals.append("naming")
    if cochange_count > 0:
        signals.append("cochange")
    if left.embedding and right.embedding:
        similarity = sum(
            left_value * right_value
            for left_value, right_value in zip(left.embedding, right.embedding, strict=True)
        )
        if similarity >= EMBEDDING_SIMILARITY_THRESHOLD:
            signals.append("embedding")
    return tuple(signals)


def _directory_key(path: str) -> str:
    parent = str(PurePosixPath(path).parent)
    return parent if parent != "." else "<root>"


def _name_tokens(path: str) -> frozenset[str]:
    stem = PurePosixPath(path).stem
    tokens = {
        token
        for token in _NAME_TOKEN_PATTERN.findall(stem.casefold())
        if len(token) >= 3 and token not in _GENERIC_NAME_TOKENS
    }
    return frozenset(tokens)


def _average_vectors(vectors: Sequence[Sequence[float]]) -> tuple[float, ...]:
    dimensions = len(vectors[0])
    if dimensions == 0 or any(len(vector) != dimensions for vector in vectors):
        raise ValueError("Subsystem embeddings must have one consistent non-zero dimension")
    averaged = [
        sum(vector[index] for vector in vectors) / len(vectors) for index in range(dimensions)
    ]
    magnitude = sqrt(sum(value * value for value in averaged))
    if magnitude == 0:
        raise ValueError("Subsystem embeddings cannot average to an all-zero vector")
    return tuple(value / magnitude for value in averaged)


def _confidence(*, member_count: int, qualifying_edges: int, distinct_signals: int) -> float:
    connectivity = min(1.0, qualifying_edges / max(1, member_count - 1))
    return round(min(0.95, 0.35 + 0.1 * distinct_signals + 0.2 * connectivity), 4)


def _candidate_name(members: Sequence[SubsystemFileInput], canonical_key: str) -> str:
    directories = Counter(_directory_key(member.path) for member in members)
    directory, count = directories.most_common(1)[0]
    if count == len(members) and directory != "<root>":
        label = PurePosixPath(directory).name.replace("_", "-").replace("-", " ").strip()
        if label:
            return f"{label.title()} candidate"
    shared_tokens = set(_name_tokens(members[0].path))
    for member in members[1:]:
        shared_tokens &= _name_tokens(member.path)
    if shared_tokens:
        return f"{sorted(shared_tokens)[0].title()} candidate"
    return f"Subsystem {canonical_key.rsplit(':', 1)[-1][:8]}"
