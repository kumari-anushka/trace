from __future__ import annotations

import json
import re
import tomllib
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol, cast
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.github.models import SourceFile, SourceFileContent, SourceFileKind
from src.graph.canonical import architecture_summary_key, evidence_key
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
from src.repositories.models import Repository
from src.repository_versions.models import RepositoryVersion

ARCHITECTURE_FACTS_VERSION = "architecture-facts-v1"
MAX_ARCHITECTURE_FILES = 10_000
MAX_MAJOR_DEPENDENCIES = 20
MAX_CONFIRMED_SUBSYSTEMS = 100
MAX_DEPENDENCY_EVIDENCE_FILES = 20
MIN_ENTRY_POINT_SCORE = 0.7
_PYTHON_MAIN_GUARD = re.compile(r"^\s*if\s+__name__\s*==\s*(['\"])__main__\1\s*:", re.MULTILINE)
_FRAMEWORK_ENTRY_NAMES = frozenset({"__main__.py", "manage.py", "wsgi.py", "asgi.py"})
_CONVENTIONAL_ENTRY_STEMS = frozenset({"app", "cli", "index", "main", "server"})


@dataclass(frozen=True, slots=True)
class ArchitectureSymbolInput:
    name: str
    start_line: int | None = None


@dataclass(frozen=True, slots=True)
class ArchitectureFileInput:
    node_id: UUID
    canonical_key: str
    path: str
    language: str | None
    content: str | None
    source_url: str
    declarations: tuple[ArchitectureSymbolInput, ...] = ()
    degree_centrality: float | None = None


@dataclass(frozen=True, slots=True)
class ArchitectureDependencyInput:
    node_id: UUID
    canonical_key: str
    name: str
    ecosystem: str | None
    dependency_kind: str | None
    importer_node_ids: tuple[UUID, ...]
    import_edge_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class ArchitectureSubsystemInput:
    node_id: UUID
    canonical_key: str
    name: str
    status: str
    confidence: float
    member_count: int


@dataclass(frozen=True, slots=True)
class ArchitectureInput:
    files: tuple[ArchitectureFileInput, ...]
    dependencies: tuple[ArchitectureDependencyInput, ...]
    subsystems: tuple[ArchitectureSubsystemInput, ...]


@dataclass(frozen=True, slots=True)
class EntryPointCandidate:
    file_node_id: UUID
    path: str
    confidence: float
    signals: tuple[str, ...]
    evidence_source_node_id: UUID
    evidence_source_path: str
    source_url: str
    excerpt: str
    start_line: int | None = None


@dataclass(frozen=True, slots=True)
class ArchitectureFacts:
    entry_points: tuple[EntryPointCandidate, ...]
    major_dependencies: tuple[ArchitectureDependencyInput, ...]
    confirmed_subsystems: tuple[ArchitectureSubsystemInput, ...]
    central_files: tuple[ArchitectureFileInput, ...]


@dataclass(frozen=True, slots=True)
class ArchitectureBuildSummary:
    files: int
    entry_points: int
    external_dependencies: int
    major_external_dependencies: int
    subsystems: int
    confirmed_subsystems: int
    derived_edges: int
    evidence: int
    stale_edges: int
    algorithm_version: str = ARCHITECTURE_FACTS_VERSION


class ArchitectureReader(Protocol):
    async def read(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> ArchitectureInput: ...


class ArchitectureStore(Protocol):
    async def prune_summary_edges(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        summary_node_id: UUID,
        retained_target_node_ids: Sequence[UUID],
    ) -> int: ...


class PostgresArchitectureStore:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def read(self, *, repository_id: UUID, repository_version_id: UUID) -> ArchitectureInput:
        repository_row = await self.session.execute(
            select(Repository.github_url, RepositoryVersion.commit_sha)
            .join(RepositoryVersion, RepositoryVersion.repository_id == Repository.id)
            .where(
                Repository.id == repository_id,
                RepositoryVersion.id == repository_version_id,
            )
        )
        github_url, commit_sha = repository_row.one()
        node_rows = await self.session.execute(
            select(GraphNode)
            .where(
                GraphNode.repository_id == repository_id,
                GraphNode.repository_version_id == repository_version_id,
                GraphNode.entity_type.in_(
                    (
                        EntityType.FILE,
                        EntityType.SYMBOL,
                        EntityType.EXTERNAL_DEPENDENCY,
                        EntityType.SUBSYSTEM,
                    )
                ),
            )
            .order_by(GraphNode.canonical_key)
        )
        nodes = list(node_rows.scalars().all())
        nodes_by_id = {node.id: node for node in nodes}
        file_nodes = {
            cast(str, node.details["path"]): node
            for node in nodes
            if node.entity_type == EntityType.FILE
            and node.details.get("file_kind") == SourceFileKind.SOURCE
            and isinstance(node.details.get("path"), str)
        }
        if len(file_nodes) > MAX_ARCHITECTURE_FILES:
            raise ValueError(
                f"Architecture file limit exceeded: {len(file_nodes)} > {MAX_ARCHITECTURE_FILES}"
            )

        content_rows = await self.session.execute(
            select(SourceFile.path, SourceFileContent.content)
            .join(SourceFileContent, SourceFileContent.source_file_id == SourceFile.id)
            .where(SourceFile.repository_version_id == repository_version_id)
        )
        content_by_path: dict[str, str] = {path: content for path, content in content_rows.all()}
        edge_rows = await self.session.execute(
            select(GraphEdge).where(
                GraphEdge.repository_id == repository_id,
                GraphEdge.repository_version_id == repository_version_id,
                GraphEdge.relationship_type.in_(
                    (RelationshipType.DECLARES, RelationshipType.IMPORTS)
                ),
            )
        )
        declarations: dict[UUID, list[ArchitectureSymbolInput]] = defaultdict(list)
        importers: dict[UUID, list[tuple[UUID, UUID]]] = defaultdict(list)
        for edge in edge_rows.scalars().all():
            target = nodes_by_id.get(edge.target_node_id)
            if target is None:
                continue
            if edge.relationship_type == RelationshipType.DECLARES:
                start_line = target.details.get("start_line")
                declarations[edge.source_node_id].append(
                    ArchitectureSymbolInput(
                        name=target.name,
                        start_line=start_line if isinstance(start_line, int) else None,
                    )
                )
            elif target.entity_type == EntityType.EXTERNAL_DEPENDENCY:
                importers[target.id].append((edge.source_node_id, edge.id))

        metric_rows = await self.session.execute(
            select(GraphMetric).where(
                GraphMetric.repository_id == repository_id,
                GraphMetric.repository_version_id == repository_version_id,
                GraphMetric.metric_name == "degree_centrality",
            )
        )
        centrality = {
            metric.node_id: metric.value
            for metric in metric_rows.scalars().all()
            if metric.node_id is not None
        }
        files = tuple(
            ArchitectureFileInput(
                node_id=node.id,
                canonical_key=node.canonical_key,
                path=path,
                language=(
                    cast(str, node.details["language"])
                    if isinstance(node.details.get("language"), str)
                    else None
                ),
                content=content_by_path.get(path),
                source_url=_source_url(github_url, commit_sha, path),
                declarations=tuple(
                    sorted(
                        declarations.get(node.id, ()),
                        key=lambda item: (item.name, item.start_line or 0),
                    )
                ),
                degree_centrality=centrality.get(node.id),
            )
            for path, node in sorted(file_nodes.items())
        )
        dependencies = tuple(
            ArchitectureDependencyInput(
                node_id=node.id,
                canonical_key=node.canonical_key,
                name=node.name,
                ecosystem=(
                    cast(str, node.details["ecosystem"])
                    if isinstance(node.details.get("ecosystem"), str)
                    else None
                ),
                dependency_kind=(
                    cast(str, node.details["dependency_kind"])
                    if isinstance(node.details.get("dependency_kind"), str)
                    else None
                ),
                importer_node_ids=tuple(
                    sorted({source_id for source_id, _ in importers.get(node.id, ())}, key=str)
                ),
                import_edge_ids=tuple(
                    sorted({edge_id for _, edge_id in importers.get(node.id, ())}, key=str)
                ),
            )
            for node in nodes
            if node.entity_type == EntityType.EXTERNAL_DEPENDENCY
        )
        subsystems = tuple(
            ArchitectureSubsystemInput(
                node_id=node.id,
                canonical_key=node.canonical_key,
                name=node.name,
                status=(
                    cast(str, node.details["status"])
                    if isinstance(node.details.get("status"), str)
                    else "candidate"
                ),
                confidence=node.confidence,
                member_count=(
                    cast(int, node.details["member_count"])
                    if isinstance(node.details.get("member_count"), int)
                    else 0
                ),
            )
            for node in nodes
            if node.entity_type == EntityType.SUBSYSTEM
        )
        return ArchitectureInput(files=files, dependencies=dependencies, subsystems=subsystems)

    async def prune_summary_edges(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        summary_node_id: UUID,
        retained_target_node_ids: Sequence[UUID],
    ) -> int:
        statement = delete(GraphEdge).where(
            GraphEdge.repository_id == repository_id,
            GraphEdge.repository_version_id == repository_version_id,
            GraphEdge.source_node_id == summary_node_id,
            GraphEdge.relationship_type == RelationshipType.DERIVED_FROM,
        )
        if retained_target_node_ids:
            statement = statement.where(GraphEdge.target_node_id.not_in(retained_target_node_ids))
        result = await self.session.execute(statement)
        return int(getattr(result, "rowcount", 0) or 0)


class DeterministicArchitectureAnalyzer:
    def analyze(self, data: ArchitectureInput) -> ArchitectureFacts:
        return ArchitectureFacts(
            entry_points=_entry_points(data.files),
            major_dependencies=tuple(
                sorted(
                    (
                        dependency
                        for dependency in data.dependencies
                        if dependency.dependency_kind != "standard_library"
                        and dependency.importer_node_ids
                    ),
                    key=lambda item: (
                        -len(item.importer_node_ids),
                        item.ecosystem or "",
                        item.name,
                    ),
                )[:MAX_MAJOR_DEPENDENCIES]
            ),
            confirmed_subsystems=tuple(
                sorted(
                    (subsystem for subsystem in data.subsystems if subsystem.status == "confirmed"),
                    key=lambda item: (-item.confidence, item.canonical_key),
                )[:MAX_CONFIRMED_SUBSYSTEMS]
            ),
            central_files=tuple(
                sorted(
                    (file for file in data.files if file.degree_centrality is not None),
                    key=lambda item: (-(item.degree_centrality or 0.0), item.path),
                )[:10]
            ),
        )


class ArchitectureBuilder:
    def __init__(
        self,
        *,
        graph_repository: GraphRepository,
        reader: ArchitectureReader,
        store: ArchitectureStore,
        analyzer: DeterministicArchitectureAnalyzer | None = None,
    ) -> None:
        self.graph_repository = graph_repository
        self.reader = reader
        self.store = store
        self.analyzer = analyzer or DeterministicArchitectureAnalyzer()

    async def build(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> ArchitectureBuildSummary:
        data = await self.reader.read(
            repository_id=repository_id, repository_version_id=repository_version_id
        )
        facts = self.analyzer.analyze(data)
        provenance: dict[str, object] = {
            "component": "architecture_analysis",
            "algorithm": ARCHITECTURE_FACTS_VERSION,
            "kind": "deterministic_fact_synthesis",
        }
        summary_node = await self.graph_repository.upsert_node(
            GraphNodeInput(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                entity_type=EntityType.ARCHITECTURE_SUMMARY,
                canonical_key=architecture_summary_key(repository_id, repository_version_id),
                name="Repository architecture",
                description=_render_description(data, facts),
                knowledge_kind=KnowledgeKind.DERIVED,
                confidence=1.0,
                provenance=provenance,
                metadata=_summary_metadata(data, facts),
            )
        )
        retained_targets: list[UUID] = []
        evidence_count = 0

        for entry_point in facts.entry_points:
            edge = await self._upsert_fact_edge(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                summary_node_id=summary_node.id,
                target_node_id=entry_point.file_node_id,
                confidence=entry_point.confidence,
                fact_kind="entry_point",
                metadata={"path": entry_point.path, "signals": list(entry_point.signals)},
                provenance=provenance,
            )
            retained_targets.append(entry_point.file_node_id)
            await self.graph_repository.upsert_evidence(
                GraphEvidenceInput(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    canonical_key=evidence_key(
                        repository_id,
                        repository_version_id,
                        summary_node.canonical_key,
                        entry_point.path,
                        "entry_point",
                        ARCHITECTURE_FACTS_VERSION,
                    ),
                    source_node_id=entry_point.evidence_source_node_id,
                    target_edge_id=edge.id,
                    evidence_type=EvidenceType.SOURCE_SPAN,
                    relationship=RelationshipType.DERIVED_FROM,
                    excerpt=entry_point.excerpt,
                    source_url=entry_point.source_url,
                    start_line=entry_point.start_line,
                    end_line=entry_point.start_line,
                    confidence=entry_point.confidence,
                    provenance=provenance,
                    metadata={
                        "fact_kind": "entry_point",
                        "source_path": entry_point.evidence_source_path,
                        "signals": list(entry_point.signals),
                    },
                )
            )
            evidence_count += 1

        files_by_id = {file.node_id: file for file in data.files}
        for dependency in facts.major_dependencies:
            edge = await self._upsert_fact_edge(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                summary_node_id=summary_node.id,
                target_node_id=dependency.node_id,
                confidence=1.0,
                fact_kind="external_dependency",
                metadata={
                    "name": dependency.name,
                    "ecosystem": dependency.ecosystem,
                    "importer_count": len(dependency.importer_node_ids),
                },
                provenance=provenance,
            )
            retained_targets.append(dependency.node_id)
            for importer_id in dependency.importer_node_ids[:MAX_DEPENDENCY_EVIDENCE_FILES]:
                importer = files_by_id.get(importer_id)
                if importer is None:
                    continue
                await self.graph_repository.upsert_evidence(
                    GraphEvidenceInput(
                        repository_id=repository_id,
                        repository_version_id=repository_version_id,
                        canonical_key=evidence_key(
                            repository_id,
                            repository_version_id,
                            summary_node.canonical_key,
                            dependency.canonical_key,
                            importer.canonical_key,
                            ARCHITECTURE_FACTS_VERSION,
                        ),
                        source_node_id=importer.node_id,
                        target_edge_id=edge.id,
                        evidence_type=EvidenceType.GRAPH_PATH,
                        relationship=RelationshipType.DERIVED_FROM,
                        excerpt=f"{importer.path} imports {dependency.name}",
                        source_url=importer.source_url,
                        confidence=1.0,
                        provenance=provenance,
                        metadata={
                            "fact_kind": "external_dependency",
                            "import_edge_ids": [str(item) for item in dependency.import_edge_ids],
                        },
                    )
                )
                evidence_count += 1

        for subsystem in facts.confirmed_subsystems:
            edge = await self._upsert_fact_edge(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                summary_node_id=summary_node.id,
                target_node_id=subsystem.node_id,
                confidence=subsystem.confidence,
                fact_kind="subsystem",
                metadata={"status": subsystem.status, "member_count": subsystem.member_count},
                provenance=provenance,
            )
            retained_targets.append(subsystem.node_id)
            await self.graph_repository.upsert_evidence(
                GraphEvidenceInput(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    canonical_key=evidence_key(
                        repository_id,
                        repository_version_id,
                        summary_node.canonical_key,
                        subsystem.canonical_key,
                        ARCHITECTURE_FACTS_VERSION,
                    ),
                    source_node_id=subsystem.node_id,
                    target_edge_id=edge.id,
                    evidence_type=EvidenceType.METRIC,
                    relationship=RelationshipType.DERIVED_FROM,
                    excerpt=(
                        f"Confirmed subsystem {subsystem.name} contains "
                        f"{subsystem.member_count} files"
                    ),
                    confidence=subsystem.confidence,
                    provenance=provenance,
                    metadata={"fact_kind": "subsystem", "status": subsystem.status},
                )
            )
            evidence_count += 1

        stale_edges = await self.store.prune_summary_edges(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            summary_node_id=summary_node.id,
            retained_target_node_ids=retained_targets,
        )
        return ArchitectureBuildSummary(
            files=len(data.files),
            entry_points=len(facts.entry_points),
            external_dependencies=len(data.dependencies),
            major_external_dependencies=len(facts.major_dependencies),
            subsystems=len(data.subsystems),
            confirmed_subsystems=len(facts.confirmed_subsystems),
            derived_edges=len(retained_targets),
            evidence=evidence_count,
            stale_edges=stale_edges,
        )

    async def _upsert_fact_edge(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        summary_node_id: UUID,
        target_node_id: UUID,
        confidence: float,
        fact_kind: str,
        metadata: dict[str, object],
        provenance: dict[str, object],
    ) -> GraphEdge:
        return await self.graph_repository.upsert_edge(
            GraphEdgeInput(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                source_node_id=summary_node_id,
                target_node_id=target_node_id,
                relationship_type=RelationshipType.DERIVED_FROM,
                knowledge_kind=KnowledgeKind.DERIVED,
                confidence=confidence,
                provenance=provenance,
                metadata={"fact_kind": fact_kind, **metadata},
            )
        )


@dataclass(slots=True)
class _MutableEntryPoint:
    file: ArchitectureFileInput
    score: float = 0.0
    signals: set[str] | None = None
    evidence_file: ArchitectureFileInput | None = None
    excerpt: str | None = None
    start_line: int | None = None

    def add(
        self,
        signal: str,
        weight: float,
        *,
        evidence_file: ArchitectureFileInput | None = None,
        excerpt: str | None = None,
        start_line: int | None = None,
    ) -> None:
        if self.signals is None:
            self.signals = set()
        if signal not in self.signals:
            self.score = min(1.0, self.score + weight)
            self.signals.add(signal)
        if evidence_file is not None and (self.evidence_file is None or weight >= 0.9):
            self.evidence_file = evidence_file
            self.excerpt = excerpt
            self.start_line = start_line


def _entry_points(files: Sequence[ArchitectureFileInput]) -> tuple[EntryPointCandidate, ...]:
    files_by_path = {file.path: file for file in files}
    candidates = {file.path: _MutableEntryPoint(file=file) for file in files}
    for file in files:
        candidate = candidates[file.path]
        path = PurePosixPath(file.path)
        name = path.name.lower()
        stem = path.stem.lower()
        if name in _FRAMEWORK_ENTRY_NAMES:
            candidate.add(
                "framework_entry_filename",
                0.85,
                evidence_file=file,
                excerpt=file.path,
            )
        elif stem in _CONVENTIONAL_ENTRY_STEMS and len(path.parts) <= 3:
            candidate.add("conventional_entry_filename", 0.35)
        for symbol in file.declarations:
            if symbol.name == "main":
                candidate.add(
                    "main_declaration",
                    0.5,
                    evidence_file=file,
                    excerpt="main declaration",
                    start_line=symbol.start_line,
                )
        if file.content:
            guard = _PYTHON_MAIN_GUARD.search(file.content)
            if guard:
                candidate.add(
                    "python_main_guard",
                    0.95,
                    evidence_file=file,
                    excerpt=guard.group(0).strip(),
                    start_line=_line_number(file.content, guard.start()),
                )
            first_line = file.content.splitlines()[0] if file.content.splitlines() else ""
            if first_line.startswith("#!") and "node" in first_line:
                candidate.add(
                    "node_executable_shebang",
                    0.95,
                    evidence_file=file,
                    excerpt=first_line,
                    start_line=1,
                )

    for manifest in files:
        for target_path, excerpt in _manifest_entry_paths(manifest, files_by_path):
            candidates[target_path].add(
                "manifest_entry",
                1.0,
                evidence_file=manifest,
                excerpt=excerpt,
                start_line=_find_line(manifest.content, excerpt),
            )

    result = []
    for item in candidates.values():
        if item.score < MIN_ENTRY_POINT_SCORE:
            continue
        evidence_file = item.evidence_file or item.file
        result.append(
            EntryPointCandidate(
                file_node_id=item.file.node_id,
                path=item.file.path,
                confidence=item.score,
                signals=tuple(sorted(item.signals or ())),
                evidence_source_node_id=evidence_file.node_id,
                evidence_source_path=evidence_file.path,
                source_url=evidence_file.source_url,
                excerpt=item.excerpt or item.file.path,
                start_line=item.start_line,
            )
        )
    return tuple(sorted(result, key=lambda item: (-item.confidence, item.path)))


def _manifest_entry_paths(
    manifest: ArchitectureFileInput,
    files_by_path: dict[str, ArchitectureFileInput],
) -> tuple[tuple[str, str], ...]:
    if not manifest.content:
        return ()
    values: list[tuple[str, str]] = []
    try:
        if PurePosixPath(manifest.path).name == "package.json":
            payload = json.loads(manifest.content)
            if not isinstance(payload, dict):
                return ()
            for field in ("main", "module"):
                value = payload.get(field)
                if isinstance(value, str):
                    values.append((value, f'"{field}": "{value}"'))
            bin_value = payload.get("bin")
            if isinstance(bin_value, str):
                values.append((bin_value, f'"bin": "{bin_value}"'))
            elif isinstance(bin_value, dict):
                values.extend(
                    (value, f'"bin": "{name}" -> "{value}"')
                    for name, value in bin_value.items()
                    if isinstance(name, str) and isinstance(value, str)
                )
        elif PurePosixPath(manifest.path).name == "pyproject.toml":
            payload = tomllib.loads(manifest.content)
            project = payload.get("project")
            if isinstance(project, dict):
                for field in ("scripts", "gui-scripts"):
                    scripts = project.get(field)
                    if isinstance(scripts, dict):
                        values.extend(
                            (value.split(":", 1)[0], f"{name} = {value}")
                            for name, value in scripts.items()
                            if isinstance(name, str) and isinstance(value, str)
                        )
            tool = payload.get("tool")
            poetry = tool.get("poetry") if isinstance(tool, dict) else None
            scripts = poetry.get("scripts") if isinstance(poetry, dict) else None
            if isinstance(scripts, dict):
                values.extend(
                    (value.split(":", 1)[0], f"{name} = {value}")
                    for name, value in scripts.items()
                    if isinstance(name, str) and isinstance(value, str)
                )
    except (json.JSONDecodeError, tomllib.TOMLDecodeError):
        return ()

    resolved: list[tuple[str, str]] = []
    manifest_parent = PurePosixPath(manifest.path).parent
    for value, excerpt in values:
        target = _resolve_manifest_path(value, manifest_parent, files_by_path)
        if target is not None:
            resolved.append((target, excerpt))
    return tuple(resolved)


def _resolve_manifest_path(
    value: str,
    manifest_parent: PurePosixPath,
    files_by_path: dict[str, ArchitectureFileInput],
) -> str | None:
    normalized = value.strip().removeprefix("./")
    if not normalized:
        return None
    relative = (manifest_parent / normalized).as_posix()
    module_path = normalized.replace(".", "/")
    candidates = [relative, normalized]
    for base in (relative, normalized, module_path, f"src/{module_path}"):
        candidates.extend(
            (
                f"{base}.py",
                f"{base}.js",
                f"{base}.mjs",
                f"{base}.cjs",
                f"{base}.ts",
                f"{base}.tsx",
                f"{base}/__main__.py",
                f"{base}/__init__.py",
                f"{base}/index.js",
                f"{base}/index.ts",
            )
        )
    return next((candidate for candidate in candidates if candidate in files_by_path), None)


def _summary_metadata(data: ArchitectureInput, facts: ArchitectureFacts) -> dict[str, object]:
    return {
        "status": "generated",
        "algorithm_version": ARCHITECTURE_FACTS_VERSION,
        "file_count": len(data.files),
        "entry_points": [
            {
                "node_id": str(item.file_node_id),
                "path": item.path,
                "confidence": item.confidence,
                "signals": list(item.signals),
            }
            for item in facts.entry_points
        ],
        "external_dependency_count": len(data.dependencies),
        "major_external_dependencies": [
            {
                "node_id": str(item.node_id),
                "name": item.name,
                "ecosystem": item.ecosystem,
                "importer_count": len(item.importer_node_ids),
            }
            for item in facts.major_dependencies
        ],
        "subsystem_count": len(data.subsystems),
        "confirmed_subsystems": [
            {
                "node_id": str(item.node_id),
                "name": item.name,
                "confidence": item.confidence,
                "member_count": item.member_count,
            }
            for item in facts.confirmed_subsystems
        ],
        "central_files": [
            {
                "node_id": str(item.node_id),
                "path": item.path,
                "degree_centrality": item.degree_centrality,
            }
            for item in facts.central_files
        ],
        "limitations": [
            "Entry points are deterministic candidates, not observed runtime traces.",
            "Imports do not prove deployment topology or runtime calls.",
            "Only confirmed subsystems are included as architecture components.",
        ],
    }


def _render_description(data: ArchitectureInput, facts: ArchitectureFacts) -> str:
    parts = [
        f"Snapshot contains {len(data.files)} source files.",
        f"Detected {len(facts.entry_points)} likely entry points from explicit manifests, "
        "executable markers, declarations, and conservative filename conventions.",
        f"Detected {len(data.dependencies)} imported external dependencies; "
        f"{len(facts.major_dependencies)} non-standard-library dependencies are included "
        "as major dependency facts.",
        f"Included {len(facts.confirmed_subsystems)} confirmed subsystems from "
        f"{len(data.subsystems)} discovered subsystem records.",
        "This summary does not infer runtime calls, services, or deployment "
        "boundaries from imports.",
    ]
    return " ".join(parts)


def _line_number(content: str, offset: int) -> int:
    return content.count("\n", 0, offset) + 1


def _find_line(content: str | None, excerpt: str) -> int | None:
    if content is None:
        return None
    needle = excerpt.split(" -> ", 1)[-1].strip('"')
    offset = content.find(needle)
    return _line_number(content, offset) if offset >= 0 else None


def _source_url(github_url: str, commit_sha: str, path: str) -> str:
    encoded_path = "/".join(quote(part, safe="") for part in PurePosixPath(path).parts)
    return f"{github_url.rstrip('/')}/blob/{commit_sha}/{encoded_path}"
