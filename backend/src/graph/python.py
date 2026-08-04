from __future__ import annotations

import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.github.models import SourceFile, SourceFileContent
from src.graph.canonical import (
    evidence_key,
    external_dependency_key,
    file_key,
    symbol_key,
)
from src.graph.models import EntityType, EvidenceType, GraphEdge, GraphNode, RelationshipType
from src.graph.repository import (
    GraphEdgeInput,
    GraphEvidenceInput,
    GraphNodeInput,
    GraphRepository,
)
from src.parsers.python import (
    PYTHON_PARSER_VERSION,
    PythonImport,
    PythonParseFailure,
    PythonParser,
)


@dataclass(frozen=True, slots=True)
class PythonSourceInput:
    id: UUID
    path: str
    blob_sha: str
    file_kind: str
    size: int | None
    content: str


@dataclass(frozen=True, slots=True)
class PythonFileFailure:
    path: str
    failure: PythonParseFailure


@dataclass(frozen=True, slots=True)
class PythonGraphSummary:
    files: int
    parsed_files: int
    failed_files: int
    symbols: int
    imports: int
    internal_imports: int
    external_imports: int
    unresolved_imports: int
    failures: tuple[PythonFileFailure, ...]


class PythonSourceReader(Protocol):
    async def list_python_sources(
        self, repository_version_id: UUID
    ) -> Sequence[PythonSourceInput]: ...


class PostgresPythonSourceReader:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def list_python_sources(self, repository_version_id: UUID) -> Sequence[PythonSourceInput]:
        result = await self.session.execute(
            select(SourceFile, SourceFileContent.content)
            .join(SourceFileContent, SourceFileContent.source_file_id == SourceFile.id)
            .where(
                SourceFile.repository_version_id == repository_version_id,
                SourceFile.language == "Python",
                SourceFile.file_kind.in_(("source", "test")),
            )
            .order_by(SourceFile.path)
        )
        return [
            PythonSourceInput(
                id=source_file.id,
                path=source_file.path,
                blob_sha=source_file.blob_sha,
                file_kind=source_file.file_kind,
                size=source_file.size,
                content=content,
            )
            for source_file, content in result.all()
        ]


class PythonGraphBuilder:
    """Persist Python declarations and syntactic imports as deterministic graph facts."""

    def __init__(
        self,
        *,
        graph_repository: GraphRepository,
        source_reader: PythonSourceReader,
        parser: PythonParser | None = None,
    ) -> None:
        self.graph_repository = graph_repository
        self.source_reader = source_reader
        self.parser = parser or PythonParser()

    async def build(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
    ) -> PythonGraphSummary:
        files = sorted(
            await self.source_reader.list_python_sources(repository_version_id),
            key=lambda source_file: source_file.path,
        )
        module_index = _PythonModuleIndex(source_file.path for source_file in files)
        file_nodes: dict[str, GraphNode] = {}
        for source_file in files:
            file_nodes[source_file.path] = await self._upsert_file_node(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                source_file=source_file,
            )

        parsed_files = 0
        symbol_count = 0
        import_count = 0
        internal_imports = 0
        external_imports = 0
        unresolved_imports = 0
        failures: list[PythonFileFailure] = []
        external_nodes: dict[str, GraphNode] = {}

        for source_file in files:
            result = self.parser.parse(path=source_file.path, content=source_file.content)
            if result.failure is not None:
                failures.append(PythonFileFailure(path=source_file.path, failure=result.failure))
                continue
            parsed_files += 1
            file_node = file_nodes[source_file.path]

            unique_symbols = {symbol.qualified_name: symbol for symbol in result.symbols}
            for symbol in unique_symbols.values():
                symbol_node = await self.graph_repository.upsert_node(
                    GraphNodeInput(
                        repository_id=repository_id,
                        repository_version_id=repository_version_id,
                        entity_type=EntityType.SYMBOL,
                        canonical_key=symbol_key(
                            repository_id,
                            repository_version_id,
                            source_file.path,
                            symbol.qualified_name,
                        ),
                        name=symbol.name,
                        provenance=self._parser_provenance(source_file),
                        metadata={
                            "path": source_file.path,
                            "qualified_name": symbol.qualified_name,
                            "symbol_kind": symbol.kind.value,
                            "start_line": symbol.start_line,
                            "end_line": symbol.end_line,
                            "start_column": symbol.start_column,
                            "end_column": symbol.end_column,
                        },
                    )
                )
                edge = await self.graph_repository.upsert_edge(
                    GraphEdgeInput(
                        repository_id=repository_id,
                        repository_version_id=repository_version_id,
                        source_node_id=file_node.id,
                        target_node_id=symbol_node.id,
                        relationship_type=RelationshipType.DECLARES,
                        provenance=self._parser_provenance(source_file),
                    )
                )
                await self._upsert_source_evidence(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    source_file=source_file,
                    source_node=file_node,
                    target_edge=edge,
                    relationship=RelationshipType.DECLARES,
                    identity=(symbol.qualified_name, symbol.start_line),
                    excerpt=symbol.excerpt,
                    start_line=symbol.start_line,
                    end_line=symbol.end_line,
                )
            symbol_count += len(unique_symbols)

            for parsed_import in result.imports:
                import_count += 1
                resolution = module_index.resolve(source_file.path, parsed_import)
                target_path = resolution.path
                if target_path == source_file.path:
                    unresolved_imports += 1
                    continue
                if target_path is not None:
                    target_node = file_nodes[target_path]
                    internal_imports += 1
                elif (
                    not resolution.internal_hint
                    and parsed_import.level == 0
                    and parsed_import.module
                ):
                    dependency_name = parsed_import.module.split(".", maxsplit=1)[0]
                    external_node = external_nodes.get(dependency_name)
                    if external_node is None:
                        external_node = await self._upsert_external_dependency(
                            repository_id=repository_id,
                            repository_version_id=repository_version_id,
                            name=dependency_name,
                        )
                        external_nodes[dependency_name] = external_node
                    target_node = external_node
                    external_imports += 1
                else:
                    unresolved_imports += 1
                    continue

                provenance = {
                    **self._parser_provenance(source_file),
                    "line": parsed_import.start_line,
                }
                edge = await self.graph_repository.upsert_edge(
                    GraphEdgeInput(
                        repository_id=repository_id,
                        repository_version_id=repository_version_id,
                        source_node_id=file_node.id,
                        target_node_id=target_node.id,
                        relationship_type=RelationshipType.IMPORTS,
                        provenance=provenance,
                        metadata={
                            "module": parsed_import.module,
                            "imported_name": parsed_import.imported_name,
                            "alias": parsed_import.alias,
                            "level": parsed_import.level,
                            "scope": parsed_import.scope,
                            "resolved": target_path is not None,
                        },
                    )
                )
                await self._upsert_source_evidence(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    source_file=source_file,
                    source_node=file_node,
                    target_edge=edge,
                    relationship=RelationshipType.IMPORTS,
                    identity=(
                        parsed_import.module,
                        parsed_import.imported_name,
                        parsed_import.start_line,
                    ),
                    excerpt=parsed_import.excerpt,
                    start_line=parsed_import.start_line,
                    end_line=parsed_import.end_line,
                )

        return PythonGraphSummary(
            files=len(files),
            parsed_files=parsed_files,
            failed_files=len(failures),
            symbols=symbol_count,
            imports=import_count,
            internal_imports=internal_imports,
            external_imports=external_imports,
            unresolved_imports=unresolved_imports,
            failures=tuple(failures),
        )

    async def _upsert_file_node(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        source_file: PythonSourceInput,
    ) -> GraphNode:
        return await self.graph_repository.upsert_node(
            GraphNodeInput(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                entity_type=EntityType.FILE,
                canonical_key=file_key(repository_id, repository_version_id, source_file.path),
                name=PurePosixPath(source_file.path).name,
                provenance={
                    "kind": "provider_snapshot",
                    "provider": "github",
                    "repository_version_id": str(repository_version_id),
                    "source_file_id": str(source_file.id),
                    "blob_sha": source_file.blob_sha,
                },
                metadata={
                    "path": source_file.path,
                    "file_kind": source_file.file_kind,
                    "language": "Python",
                    "size": source_file.size,
                },
            )
        )

    async def _upsert_external_dependency(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        name: str,
    ) -> GraphNode:
        dependency_kind = "standard_library" if name in sys.stdlib_module_names else "package"
        return await self.graph_repository.upsert_node(
            GraphNodeInput(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                entity_type=EntityType.EXTERNAL_DEPENDENCY,
                canonical_key=external_dependency_key(
                    repository_id, repository_version_id, "python", name
                ),
                name=name,
                provenance={
                    "kind": "python_import",
                    "parser": "python_ast",
                    "parser_version": PYTHON_PARSER_VERSION,
                },
                metadata={"ecosystem": "python", "dependency_kind": dependency_kind},
            )
        )

    async def _upsert_source_evidence(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        source_file: PythonSourceInput,
        source_node: GraphNode,
        target_edge: GraphEdge,
        relationship: RelationshipType,
        identity: tuple[object, ...],
        excerpt: str,
        start_line: int,
        end_line: int,
    ) -> None:
        await self.graph_repository.upsert_evidence(
            GraphEvidenceInput(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                canonical_key=evidence_key(
                    repository_id,
                    repository_version_id,
                    source_file.path,
                    relationship,
                    *identity,
                ),
                source_node_id=source_node.id,
                target_edge_id=target_edge.id,
                evidence_type=EvidenceType.SOURCE_SPAN,
                relationship=relationship,
                excerpt=excerpt,
                start_line=start_line,
                end_line=end_line,
                confidence=1.0,
                provenance=self._parser_provenance(source_file),
            )
        )

    @staticmethod
    def _parser_provenance(source_file: PythonSourceInput) -> dict[str, object]:
        return {
            "kind": "source_parser",
            "parser": "python_ast",
            "parser_version": PYTHON_PARSER_VERSION,
            "source_file_id": str(source_file.id),
            "blob_sha": source_file.blob_sha,
            "path": source_file.path,
        }


class _PythonModuleIndex:
    SOURCE_ROOTS = {"src", "lib"}

    def __init__(self, paths: Iterable[str]) -> None:
        self.paths = set(paths)
        self.aliases: dict[str, str | None] = {}
        for path in sorted(self.paths):
            module_parts = self._module_parts(path)
            self._register_alias(module_parts, path)
            for index, part in enumerate(module_parts):
                if part not in self.SOURCE_ROOTS:
                    continue
                self._register_alias(module_parts[index:], path)
                self._register_alias(module_parts[index + 1 :], path)

    def resolve(self, source_path: str, parsed_import: PythonImport) -> _PythonImportResolution:
        module_parts = parsed_import.module.split(".") if parsed_import.module else []
        imported_parts = (
            [parsed_import.imported_name]
            if parsed_import.imported_name and parsed_import.imported_name != "*"
            else []
        )
        bases: list[list[str]] = []
        if parsed_import.level:
            parent_parts = list(PurePosixPath(source_path).parent.parts)
            keep = len(parent_parts) - (parsed_import.level - 1)
            if keep < 0:
                return _PythonImportResolution(path=None, internal_hint=True)
            bases.append([*parent_parts[:keep], *module_parts])
        elif module_parts:
            bases.append(module_parts)

        for base in bases:
            if imported_parts:
                resolved = self._resolve_parts([*base, *imported_parts])
                if resolved.path is not None or resolved.internal_hint:
                    return resolved
            resolved = self._resolve_parts(base)
            if resolved.path is not None or resolved.internal_hint:
                return resolved
        return _PythonImportResolution(
            path=None,
            internal_hint=parsed_import.level > 0,
        )

    def _resolve_parts(self, parts: Sequence[str]) -> _PythonImportResolution:
        if not parts:
            return _PythonImportResolution(path=None, internal_hint=False)
        alias = ".".join(parts)
        if alias not in self.aliases:
            return _PythonImportResolution(path=None, internal_hint=False)
        return _PythonImportResolution(path=self.aliases[alias], internal_hint=True)

    def _register_alias(self, parts: Sequence[str], path: str) -> None:
        if not parts:
            return
        alias = ".".join(parts)
        existing = self.aliases.get(alias)
        if existing is None and alias in self.aliases:
            return
        if existing is not None and existing != path:
            self.aliases[alias] = None
            return
        self.aliases[alias] = path

    @staticmethod
    def _module_parts(path: str) -> list[str]:
        source_path = PurePosixPath(path)
        parts = list(source_path.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts.pop()
        return parts


@dataclass(frozen=True, slots=True)
class _PythonImportResolution:
    path: str | None
    internal_hint: bool
