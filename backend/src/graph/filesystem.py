from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.github.models import SourceFile
from src.graph.canonical import directory_key, evidence_key, file_key, snapshot_key
from src.graph.models import EntityType, EvidenceType, GraphNode, RelationshipType
from src.graph.repository import (
    GraphEdgeInput,
    GraphEvidenceInput,
    GraphNodeInput,
    GraphRepository,
)

CONTAINS = RelationshipType.CONTAINS


@dataclass(frozen=True, slots=True)
class SourceFileGraphInput:
    id: UUID
    path: str
    file_kind: str
    language: str | None
    blob_sha: str
    size: int | None


@dataclass(frozen=True, slots=True)
class FilesystemGraphSummary:
    nodes: int
    edges: int
    evidence: int
    directories: int
    files: int


class SourceFileReader(Protocol):
    async def list_for_graph(
        self, repository_version_id: UUID
    ) -> Sequence[SourceFileGraphInput]: ...


class PostgresSourceFileReader:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def list_for_graph(self, repository_version_id: UUID) -> Sequence[SourceFileGraphInput]:
        result = await self.session.execute(
            select(SourceFile)
            .where(SourceFile.repository_version_id == repository_version_id)
            .order_by(SourceFile.path)
        )
        return [
            SourceFileGraphInput(
                id=source_file.id,
                path=source_file.path,
                file_kind=source_file.file_kind,
                language=source_file.language,
                blob_sha=source_file.blob_sha,
                size=source_file.size,
            )
            for source_file in result.scalars().all()
        ]


class FilesystemGraphBuilder:
    """Build the snapshot/directory/file tree solely from persisted source facts."""

    def __init__(
        self,
        *,
        graph_repository: GraphRepository,
        source_file_reader: SourceFileReader,
    ) -> None:
        self.graph_repository = graph_repository
        self.source_file_reader = source_file_reader

    async def build(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
    ) -> FilesystemGraphSummary:
        files = await self.source_file_reader.list_for_graph(repository_version_id)
        normalized_files = sorted(
            (_normalize_file(source_file) for source_file in files),
            key=lambda source_file: source_file.path,
        )
        prefix = snapshot_key(repository_id, repository_version_id)
        provenance: dict[str, object] = {
            "kind": "provider_snapshot",
            "provider": "github",
            "repository_version_id": str(repository_version_id),
        }

        snapshot_node = await self.graph_repository.upsert_node(
            GraphNodeInput(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                entity_type=EntityType.REPOSITORY_SNAPSHOT,
                canonical_key=prefix,
                name="Repository snapshot",
                provenance=provenance,
            )
        )

        directory_paths = sorted(
            {
                str(parent)
                for source_file in normalized_files
                for parent in _parents(source_file.path)
            },
            key=lambda path: (path.count("/"), path),
        )
        nodes_by_path = {}
        for path in directory_paths:
            nodes_by_path[path] = await self.graph_repository.upsert_node(
                GraphNodeInput(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    entity_type=EntityType.DIRECTORY,
                    canonical_key=directory_key(repository_id, repository_version_id, path),
                    name=PurePosixPath(path).name,
                    provenance=provenance,
                    metadata={"path": path},
                )
            )

        file_nodes = {}
        for source_file in normalized_files:
            file_nodes[source_file.path] = await self.graph_repository.upsert_node(
                GraphNodeInput(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    entity_type=EntityType.FILE,
                    canonical_key=file_key(repository_id, repository_version_id, source_file.path),
                    name=PurePosixPath(source_file.path).name,
                    provenance={
                        **provenance,
                        "source_file_id": str(source_file.id),
                        "blob_sha": source_file.blob_sha,
                    },
                    metadata={
                        "path": source_file.path,
                        "file_kind": source_file.file_kind,
                        "language": source_file.language,
                        "size": source_file.size,
                    },
                )
            )

        relations: list[tuple[GraphNode, GraphNode, str, UUID | None]] = []
        for path in directory_paths:
            parent_path = str(PurePosixPath(path).parent)
            parent_node = snapshot_node if parent_path == "." else nodes_by_path[parent_path]
            relations.append((parent_node, nodes_by_path[path], path, None))
        for source_file in normalized_files:
            parent_path = str(PurePosixPath(source_file.path).parent)
            parent_node = snapshot_node if parent_path == "." else nodes_by_path[parent_path]
            relations.append(
                (parent_node, file_nodes[source_file.path], source_file.path, source_file.id)
            )

        for parent_node, child_node, path, source_file_id in relations:
            relation_provenance: dict[str, object] = {**provenance, "path": path}
            if source_file_id is not None:
                relation_provenance["source_file_id"] = str(source_file_id)
            edge = await self.graph_repository.upsert_edge(
                GraphEdgeInput(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    source_node_id=parent_node.id,
                    target_node_id=child_node.id,
                    relationship_type=CONTAINS,
                    provenance=relation_provenance,
                )
            )
            await self.graph_repository.upsert_evidence(
                GraphEvidenceInput(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    canonical_key=evidence_key(
                        repository_id,
                        repository_version_id,
                        parent_node.canonical_key,
                        child_node.canonical_key,
                        CONTAINS,
                    ),
                    source_node_id=child_node.id,
                    target_edge_id=edge.id,
                    evidence_type=EvidenceType.PROVIDER_RELATION,
                    relationship=CONTAINS,
                    excerpt=path,
                    provenance=relation_provenance,
                )
            )

        file_count = len(normalized_files)
        directory_count = len(directory_paths)
        edge_count = len(relations)
        return FilesystemGraphSummary(
            nodes=1 + directory_count + file_count,
            edges=edge_count,
            evidence=edge_count,
            directories=directory_count,
            files=file_count,
        )


def _normalize_file(source_file: SourceFileGraphInput) -> SourceFileGraphInput:
    raw_path = source_file.path.replace("\\", "/")
    if raw_path.startswith("/"):
        raise ValueError(f"Invalid repository file path: {source_file.path!r}")
    normalized = raw_path.strip("/")
    path = PurePosixPath(normalized)
    if not normalized or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Invalid repository file path: {source_file.path!r}")
    return SourceFileGraphInput(
        id=source_file.id,
        path=str(path),
        file_kind=source_file.file_kind,
        language=source_file.language,
        blob_sha=source_file.blob_sha,
        size=source_file.size,
    )


def _parents(path: str) -> Sequence[PurePosixPath]:
    parents = PurePosixPath(path).parents
    return [parent for parent in reversed(parents) if str(parent) != "."]
