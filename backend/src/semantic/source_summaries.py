from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Protocol
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.github.models import SourceFile, SourceFileContent, SourceFileKind
from src.graph.models import EntityType, GraphEdge, GraphMetric, GraphNode, RelationshipType
from src.repositories.models import Repository
from src.repository_versions.models import RepositoryVersion
from src.semantic.documentation import DOCUMENTATION_CHUNKER_VERSION, chunk_documentation
from src.semantic.models import DocumentSourceType
from src.semantic.repository import DocumentInput, SemanticRepository

SOURCE_SUMMARY_VERSION = "source-summary-v1"
SOURCE_SUMMARY_CHUNKER_VERSION = f"{SOURCE_SUMMARY_VERSION}-{DOCUMENTATION_CHUNKER_VERSION}"
MAX_SOURCE_SUMMARY_FILES = 10_000
MAX_SUMMARY_RELATIONS = 50
MAX_RELATION_LABEL_CHARS = 240


@dataclass(frozen=True, slots=True)
class SourceSummaryRelation:
    edge_id: UUID
    entity_type: str
    name: str
    path: str | None = None
    symbol_kind: str | None = None
    qualified_name: str | None = None


@dataclass(frozen=True, slots=True)
class SourceSummaryInput:
    id: UUID
    path: str
    blob_sha: str
    file_kind: str
    language: str | None
    size: int | None
    content_hash: str | None
    source_url: str
    source_node_id: UUID | None
    declarations: tuple[SourceSummaryRelation, ...]
    imports: tuple[SourceSummaryRelation, ...]
    degree_centrality: float | None = None
    community_index: int | None = None


@dataclass(frozen=True, slots=True)
class SourceSummaryBuildSummary:
    files: int
    chunks: int
    characters: int
    declarations: int
    imports: int
    missing_graph_nodes: int
    truncated_declarations: int
    truncated_imports: int
    stale_documents: int
    algorithm_version: str = SOURCE_SUMMARY_VERSION


class SourceSummaryReader(Protocol):
    async def list_source_summary_inputs(
        self, repository_version_id: UUID
    ) -> Sequence[SourceSummaryInput]: ...


class PostgresSourceSummaryReader:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def list_source_summary_inputs(
        self, repository_version_id: UUID
    ) -> Sequence[SourceSummaryInput]:
        source_rows = await self.session.execute(
            select(
                SourceFile,
                SourceFileContent.content_hash,
                Repository.github_url,
                RepositoryVersion.commit_sha,
            )
            .outerjoin(SourceFileContent, SourceFileContent.source_file_id == SourceFile.id)
            .join(
                RepositoryVersion,
                RepositoryVersion.id == SourceFile.repository_version_id,
            )
            .join(Repository, Repository.id == RepositoryVersion.repository_id)
            .where(
                SourceFile.repository_version_id == repository_version_id,
                SourceFile.file_kind.in_((SourceFileKind.SOURCE, SourceFileKind.TEST)),
            )
            .order_by(SourceFile.path)
        )
        sources = source_rows.all()
        if len(sources) > MAX_SOURCE_SUMMARY_FILES:
            raise ValueError(
                f"Source summary file limit exceeded: {len(sources)} > {MAX_SOURCE_SUMMARY_FILES}"
            )

        node_rows = await self.session.execute(
            select(GraphNode).where(GraphNode.repository_version_id == repository_version_id)
        )
        nodes = list(node_rows.scalars().all())
        nodes_by_id = {node.id: node for node in nodes}
        file_nodes_by_path = {
            path: node
            for node in nodes
            if node.entity_type == EntityType.FILE
            and isinstance((path := node.details.get("path")), str)
        }
        file_node_ids = {node.id for node in file_nodes_by_path.values()}

        relations_by_source: dict[UUID, list[tuple[GraphEdge, GraphNode]]] = {}
        if file_node_ids:
            edge_rows = await self.session.execute(
                select(GraphEdge).where(
                    GraphEdge.repository_version_id == repository_version_id,
                    GraphEdge.source_node_id.in_(file_node_ids),
                    GraphEdge.relationship_type.in_(
                        (RelationshipType.DECLARES, RelationshipType.IMPORTS)
                    ),
                )
            )
            for edge in edge_rows.scalars().all():
                target = nodes_by_id.get(edge.target_node_id)
                if target is not None:
                    relations_by_source.setdefault(edge.source_node_id, []).append((edge, target))

        metrics_by_node: dict[UUID, dict[str, GraphMetric]] = {}
        if file_node_ids:
            metric_rows = await self.session.execute(
                select(GraphMetric).where(
                    GraphMetric.repository_version_id == repository_version_id,
                    GraphMetric.node_id.in_(file_node_ids),
                    GraphMetric.metric_name.in_(("degree_centrality", "community_membership")),
                )
            )
            for metric in metric_rows.scalars().all():
                if metric.node_id is not None:
                    metrics_by_node.setdefault(metric.node_id, {})[metric.metric_name] = metric

        result: list[SourceSummaryInput] = []
        for source_file, content_hash, github_url, commit_sha in sources:
            file_node = file_nodes_by_path.get(source_file.path)
            relations = relations_by_source.get(file_node.id, []) if file_node else []
            declarations = tuple(
                _relation(edge, target)
                for edge, target in relations
                if edge.relationship_type == RelationshipType.DECLARES
            )
            imports = tuple(
                _relation(edge, target)
                for edge, target in relations
                if edge.relationship_type == RelationshipType.IMPORTS
            )
            metrics = metrics_by_node.get(file_node.id, {}) if file_node else {}
            centrality = metrics.get("degree_centrality")
            community = metrics.get("community_membership")
            community_index = (
                community.details.get("community_index") if community is not None else None
            )
            result.append(
                SourceSummaryInput(
                    id=source_file.id,
                    path=source_file.path,
                    blob_sha=source_file.blob_sha,
                    file_kind=source_file.file_kind,
                    language=source_file.language,
                    size=source_file.size,
                    content_hash=content_hash,
                    source_url=_source_url(github_url, commit_sha, source_file.path),
                    source_node_id=file_node.id if file_node else None,
                    declarations=tuple(sorted(declarations, key=_relation_sort_key)),
                    imports=tuple(sorted(imports, key=_relation_sort_key)),
                    degree_centrality=centrality.value if centrality is not None else None,
                    community_index=(community_index if isinstance(community_index, int) else None),
                )
            )
        return result


class SourceSummaryBuilder:
    def __init__(
        self,
        *,
        semantic_repository: SemanticRepository,
        source_reader: SourceSummaryReader,
    ) -> None:
        self.semantic_repository = semantic_repository
        self.source_reader = source_reader

    async def build(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
    ) -> SourceSummaryBuildSummary:
        sources = await self.source_reader.list_source_summary_inputs(repository_version_id)
        retained_keys: list[str] = []
        chunk_count = 0
        character_count = 0
        declaration_count = 0
        import_count = 0
        missing_graph_nodes = 0
        truncated_declarations = 0
        truncated_imports = 0

        for source in sorted(sources, key=lambda item: item.path):
            declaration_count += len(source.declarations)
            import_count += len(source.imports)
            if source.source_node_id is None:
                missing_graph_nodes += 1
            selected_declarations = source.declarations[:MAX_SUMMARY_RELATIONS]
            selected_imports = source.imports[:MAX_SUMMARY_RELATIONS]
            truncated_declarations += len(source.declarations) - len(selected_declarations)
            truncated_imports += len(source.imports) - len(selected_imports)
            summary = _render_summary(
                source,
                declarations=selected_declarations,
                imports=selected_imports,
            )
            summary_hash = sha256(summary.encode()).hexdigest()
            for chunk_index, chunk in enumerate(chunk_documentation(summary)):
                canonical_key = _source_summary_key(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    path=source.path,
                    chunk_index=chunk_index,
                )
                retained_keys.append(canonical_key)
                relation_edge_ids = [
                    str(relation.edge_id)
                    for relation in (*selected_declarations, *selected_imports)
                ]
                await self.semantic_repository.upsert_document(
                    DocumentInput(
                        repository_id=repository_id,
                        repository_version_id=repository_version_id,
                        source_node_id=source.source_node_id,
                        source_type=DocumentSourceType.SOURCE_SUMMARY,
                        source_key=source.path,
                        canonical_key=canonical_key,
                        title=f"Source summary: {PurePosixPath(source.path).name}",
                        content=chunk.content,
                        chunk_index=chunk_index,
                        start_offset=chunk.start_offset,
                        end_offset=chunk.end_offset,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        source_url=source.source_url,
                        provenance={
                            "kind": "deterministic_source_summary",
                            "provider": "repository_graph",
                            "algorithm": SOURCE_SUMMARY_VERSION,
                            "chunker": SOURCE_SUMMARY_CHUNKER_VERSION,
                            "source_file_id": str(source.id),
                            "source_node_id": (
                                str(source.source_node_id) if source.source_node_id else None
                            ),
                            "relation_edge_ids": relation_edge_ids,
                            "source_content_hash": source.content_hash,
                            "summary_content_hash": summary_hash,
                        },
                        metadata={
                            "path": source.path,
                            "blob_sha": source.blob_sha,
                            "file_kind": source.file_kind,
                            "language": source.language,
                            "size": source.size,
                            "content_field": "deterministic_summary",
                            "source_content_hash": source.content_hash,
                            "summary_content_hash": summary_hash,
                            "algorithm_version": SOURCE_SUMMARY_VERSION,
                            "chunker_version": SOURCE_SUMMARY_CHUNKER_VERSION,
                            "declaration_count": len(source.declarations),
                            "import_count": len(source.imports),
                            "truncated_declarations": (
                                len(source.declarations) - len(selected_declarations)
                            ),
                            "truncated_imports": len(source.imports) - len(selected_imports),
                            "degree_centrality": source.degree_centrality,
                            "community_index": source.community_index,
                            "heading": chunk.heading,
                            "start_line": chunk.start_line,
                            "end_line": chunk.end_line,
                            "start_offset": chunk.start_offset,
                            "end_offset": chunk.end_offset,
                        },
                    )
                )
                chunk_count += 1
                character_count += len(chunk.content)

        stale_documents = await self.semantic_repository.prune_documents(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            source_type=DocumentSourceType.SOURCE_SUMMARY,
            retained_canonical_keys=retained_keys,
        )
        return SourceSummaryBuildSummary(
            files=len(sources),
            chunks=chunk_count,
            characters=character_count,
            declarations=declaration_count,
            imports=import_count,
            missing_graph_nodes=missing_graph_nodes,
            truncated_declarations=truncated_declarations,
            truncated_imports=truncated_imports,
            stale_documents=stale_documents,
        )


def _relation(edge: GraphEdge, target: GraphNode) -> SourceSummaryRelation:
    path = target.details.get("path")
    symbol_kind = target.details.get("symbol_kind")
    qualified_name = target.details.get("qualified_name")
    return SourceSummaryRelation(
        edge_id=edge.id,
        entity_type=target.entity_type,
        name=target.name,
        path=path if isinstance(path, str) else None,
        symbol_kind=symbol_kind if isinstance(symbol_kind, str) else None,
        qualified_name=qualified_name if isinstance(qualified_name, str) else None,
    )


def _relation_sort_key(relation: SourceSummaryRelation) -> tuple[str, str, str, str]:
    return (
        relation.entity_type,
        relation.path or "",
        relation.qualified_name or "",
        relation.name,
    )


def _render_summary(
    source: SourceSummaryInput,
    *,
    declarations: Sequence[SourceSummaryRelation],
    imports: Sequence[SourceSummaryRelation],
) -> str:
    lines = [
        f"# {source.path}",
        "",
        f"File kind: {source.file_kind}",
        f"Language: {source.language or 'Unknown'}",
        f"Blob SHA: {source.blob_sha}",
    ]
    if source.content_hash:
        lines.append(f"Content hash: {source.content_hash}")
    if source.size is not None:
        lines.append(f"Size: {source.size} bytes")

    lines.extend(("", "## Declares"))
    if declarations:
        lines.extend(f"- {_declaration_label(item)}" for item in declarations)
    else:
        lines.append("- None detected")
    omitted_declarations = len(source.declarations) - len(declarations)
    if omitted_declarations:
        lines.append(f"- … {omitted_declarations} additional declarations omitted")

    lines.extend(("", "## Imports"))
    if imports:
        lines.extend(f"- {_import_label(item)}" for item in imports)
    else:
        lines.append("- None detected")
    omitted_imports = len(source.imports) - len(imports)
    if omitted_imports:
        lines.append(f"- … {omitted_imports} additional imports omitted")

    lines.extend(("", "## Structural metrics"))
    lines.append(
        "- Degree centrality: "
        + (f"{source.degree_centrality:.6f}" if source.degree_centrality is not None else "Unknown")
    )
    lines.append(
        "- Import community: "
        + (str(source.community_index) if source.community_index is not None else "Unknown")
    )
    return "\n".join(lines) + "\n"


def _declaration_label(relation: SourceSummaryRelation) -> str:
    kind = relation.symbol_kind or relation.entity_type
    name = relation.qualified_name or relation.name
    return _bounded_label(f"{kind}: {name}")


def _import_label(relation: SourceSummaryRelation) -> str:
    if relation.entity_type == EntityType.FILE:
        return _bounded_label(f"internal file: {relation.path or relation.name}")
    if relation.entity_type == EntityType.EXTERNAL_DEPENDENCY:
        return _bounded_label(f"external dependency: {relation.name}")
    return _bounded_label(f"{relation.entity_type}: {relation.name}")


def _bounded_label(value: str) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= MAX_RELATION_LABEL_CHARS:
        return normalized
    return normalized[: MAX_RELATION_LABEL_CHARS - 1].rstrip() + "…"


def _source_summary_key(
    *,
    repository_id: UUID,
    repository_version_id: UUID,
    path: str,
    chunk_index: int,
) -> str:
    identity = f"{path}\0{chunk_index}\0{SOURCE_SUMMARY_CHUNKER_VERSION}"
    digest = sha256(identity.encode()).hexdigest()
    return f"repo:{repository_id}:snapshot:{repository_version_id}:source-summary:{digest}"


def _source_url(github_url: str, commit_sha: str, path: str) -> str:
    quoted_path = quote(path, safe="/")
    return f"{github_url.rstrip('/')}/blob/{commit_sha}/{quoted_path}"
