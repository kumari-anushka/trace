from __future__ import annotations

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
from src.parsers.javascript import (
    JAVASCRIPT_PARSER_VERSION,
    JavaScriptExport,
    JavaScriptParseFailure,
    JavaScriptParser,
)

NODE_BUILTINS = frozenset(
    {
        "assert",
        "buffer",
        "child_process",
        "cluster",
        "console",
        "crypto",
        "dgram",
        "dns",
        "events",
        "fs",
        "http",
        "https",
        "module",
        "net",
        "os",
        "path",
        "perf_hooks",
        "process",
        "querystring",
        "readline",
        "stream",
        "string_decoder",
        "timers",
        "tls",
        "tty",
        "url",
        "util",
        "v8",
        "vm",
        "worker_threads",
        "zlib",
    }
)


@dataclass(frozen=True, slots=True)
class JavaScriptSourceInput:
    id: UUID
    path: str
    blob_sha: str
    file_kind: str
    language: str
    size: int | None
    content: str


@dataclass(frozen=True, slots=True)
class JavaScriptFileFailure:
    path: str
    failure: JavaScriptParseFailure


@dataclass(frozen=True, slots=True)
class JavaScriptGraphSummary:
    files: int
    parsed_files: int
    failed_files: int
    symbols: int
    imports: int
    exports: int
    components: int
    hooks: int
    internal_imports: int
    external_imports: int
    unresolved_imports: int
    failures: tuple[JavaScriptFileFailure, ...]


class JavaScriptSourceReader(Protocol):
    async def list_javascript_sources(
        self, repository_version_id: UUID
    ) -> Sequence[JavaScriptSourceInput]: ...


class PostgresJavaScriptSourceReader:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def list_javascript_sources(
        self, repository_version_id: UUID
    ) -> Sequence[JavaScriptSourceInput]:
        result = await self.session.execute(
            select(SourceFile, SourceFileContent.content)
            .join(SourceFileContent, SourceFileContent.source_file_id == SourceFile.id)
            .where(
                SourceFile.repository_version_id == repository_version_id,
                SourceFile.language.in_(("TypeScript", "JavaScript")),
                SourceFile.file_kind.in_(("source", "test")),
            )
            .order_by(SourceFile.path)
        )
        return [
            JavaScriptSourceInput(
                id=source_file.id,
                path=source_file.path,
                blob_sha=source_file.blob_sha,
                file_kind=source_file.file_kind,
                language=source_file.language or "JavaScript",
                size=source_file.size,
                content=content,
            )
            for source_file, content in result.all()
        ]


class JavaScriptGraphBuilder:
    """Persist JS/TS declarations, import relations, and export evidence."""

    def __init__(
        self,
        *,
        graph_repository: GraphRepository,
        source_reader: JavaScriptSourceReader,
        parser: JavaScriptParser | None = None,
    ) -> None:
        self.graph_repository = graph_repository
        self.source_reader = source_reader
        self.parser = parser or JavaScriptParser()

    async def build(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
    ) -> JavaScriptGraphSummary:
        files = sorted(
            await self.source_reader.list_javascript_sources(repository_version_id),
            key=lambda source_file: source_file.path,
        )
        module_index = _JavaScriptModuleIndex(source_file.path for source_file in files)
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
        export_count = 0
        component_count = 0
        hook_count = 0
        internal_imports = 0
        external_imports = 0
        unresolved_imports = 0
        failures: list[JavaScriptFileFailure] = []
        external_nodes: dict[str, GraphNode] = {}

        for source_file in files:
            result = self.parser.parse(path=source_file.path, content=source_file.content)
            if result.failure is not None:
                failures.append(
                    JavaScriptFileFailure(path=source_file.path, failure=result.failure)
                )
                continue
            parsed_files += 1
            file_node = file_nodes[source_file.path]
            unique_symbols = {symbol.qualified_name: symbol for symbol in result.symbols}
            symbol_nodes: dict[str, GraphNode] = {}

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
                            "language": source_file.language,
                            "qualified_name": symbol.qualified_name,
                            "symbol_kind": symbol.kind.value,
                            "start_line": symbol.start_line,
                            "end_line": symbol.end_line,
                            "start_column": symbol.start_column,
                            "end_column": symbol.end_column,
                            "exported": symbol.exported,
                            "default_export": symbol.default_export,
                            "is_component": symbol.is_component,
                            "is_hook": symbol.is_hook,
                        },
                    )
                )
                symbol_nodes[symbol.name] = symbol_node
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
                await self._upsert_edge_evidence(
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
            component_count += sum(symbol.is_component for symbol in unique_symbols.values())
            hook_count += sum(symbol.is_hook for symbol in unique_symbols.values())

            for parsed_import in result.imports:
                import_count += 1
                resolution = module_index.resolve(
                    source_path=source_file.path,
                    module=parsed_import.module,
                )
                if resolution.path == source_file.path:
                    unresolved_imports += 1
                    continue
                if resolution.path is not None:
                    target_node = file_nodes[resolution.path]
                    internal_imports += 1
                elif not resolution.internal_hint:
                    dependency_name = _dependency_name(parsed_import.module)
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
                            "local_name": parsed_import.local_name,
                            "import_kind": parsed_import.kind.value,
                            "type_only": parsed_import.type_only,
                            "scope": parsed_import.scope,
                            "resolved": resolution.path is not None,
                        },
                    )
                )
                await self._upsert_edge_evidence(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    source_file=source_file,
                    source_node=file_node,
                    target_edge=edge,
                    relationship=RelationshipType.IMPORTS,
                    identity=(
                        parsed_import.module,
                        parsed_import.imported_name,
                        parsed_import.kind,
                        parsed_import.start_line,
                    ),
                    excerpt=parsed_import.excerpt,
                    start_line=parsed_import.start_line,
                    end_line=parsed_import.end_line,
                )

            for exported in result.exports:
                export_count += 1
                target_node = (
                    symbol_nodes.get(exported.local_name)
                    if exported.local_name is not None
                    else None
                ) or file_node
                await self._upsert_export_evidence(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    source_file=source_file,
                    source_node=file_node,
                    target_node=target_node,
                    exported=exported,
                )

        return JavaScriptGraphSummary(
            files=len(files),
            parsed_files=parsed_files,
            failed_files=len(failures),
            symbols=symbol_count,
            imports=import_count,
            exports=export_count,
            components=component_count,
            hooks=hook_count,
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
        source_file: JavaScriptSourceInput,
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
                    "language": source_file.language,
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
        bare_name = name.removeprefix("node:")
        is_builtin = name.startswith("node:") or bare_name in NODE_BUILTINS
        ecosystem = "node" if is_builtin else "npm"
        return await self.graph_repository.upsert_node(
            GraphNodeInput(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                entity_type=EntityType.EXTERNAL_DEPENDENCY,
                canonical_key=external_dependency_key(
                    repository_id, repository_version_id, ecosystem, name
                ),
                name=name,
                provenance={
                    "kind": "javascript_import",
                    "parser": "tree_sitter_javascript_typescript",
                    "parser_version": JAVASCRIPT_PARSER_VERSION,
                },
                metadata={
                    "ecosystem": ecosystem,
                    "dependency_kind": "standard_library" if is_builtin else "package",
                },
            )
        )

    async def _upsert_edge_evidence(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        source_file: JavaScriptSourceInput,
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
                provenance=self._parser_provenance(source_file),
            )
        )

    async def _upsert_export_evidence(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        source_file: JavaScriptSourceInput,
        source_node: GraphNode,
        target_node: GraphNode,
        exported: JavaScriptExport,
    ) -> None:
        await self.graph_repository.upsert_evidence(
            GraphEvidenceInput(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                canonical_key=evidence_key(
                    repository_id,
                    repository_version_id,
                    source_file.path,
                    "EXPORT",
                    exported.name,
                    exported.local_name,
                    exported.source,
                    exported.start_line,
                ),
                source_node_id=source_node.id,
                target_node_id=target_node.id,
                evidence_type=EvidenceType.SOURCE_SPAN,
                excerpt=exported.excerpt,
                start_line=exported.start_line,
                end_line=exported.end_line,
                provenance=self._parser_provenance(source_file),
                metadata={
                    "fact": "export",
                    "name": exported.name,
                    "local_name": exported.local_name,
                    "source": exported.source,
                    "default": exported.default,
                    "type_only": exported.type_only,
                },
            )
        )

    @staticmethod
    def _parser_provenance(source_file: JavaScriptSourceInput) -> dict[str, object]:
        return {
            "kind": "source_parser",
            "parser": "tree_sitter_javascript_typescript",
            "parser_version": JAVASCRIPT_PARSER_VERSION,
            "source_file_id": str(source_file.id),
            "blob_sha": source_file.blob_sha,
            "path": source_file.path,
        }


@dataclass(frozen=True, slots=True)
class _JavaScriptImportResolution:
    path: str | None
    internal_hint: bool


class _JavaScriptModuleIndex:
    SOURCE_ROOTS = {"src", "lib"}
    EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}

    def __init__(self, paths: Iterable[str]) -> None:
        self.aliases: dict[str, str | None] = {}
        for path in sorted(paths):
            parts = self._module_parts(path)
            self._register_alias(parts, path)
            for index, part in enumerate(parts):
                if part not in self.SOURCE_ROOTS:
                    continue
                self._register_alias(parts[index:], path)
                self._register_alias(parts[index + 1 :], path)

    def resolve(self, *, source_path: str, module: str) -> _JavaScriptImportResolution:
        if module.startswith("."):
            parent_parts = list(PurePosixPath(source_path).parent.parts)
            parts = self._normalize_parts([*parent_parts, *module.split("/")])
            return self._resolve_alias(parts, internal_hint=True)
        if module.startswith(("@/", "~/", "/")):
            return _JavaScriptImportResolution(path=None, internal_hint=True)
        parts = self._normalize_parts(module.split("/"))
        return self._resolve_alias(parts, internal_hint=False)

    def _resolve_alias(
        self, parts: Sequence[str], *, internal_hint: bool
    ) -> _JavaScriptImportResolution:
        alias = "/".join(parts)
        if alias not in self.aliases:
            return _JavaScriptImportResolution(path=None, internal_hint=internal_hint)
        return _JavaScriptImportResolution(path=self.aliases[alias], internal_hint=True)

    def _register_alias(self, parts: Sequence[str], path: str) -> None:
        if not parts:
            return
        alias = "/".join(parts)
        existing = self.aliases.get(alias)
        if existing is None and alias in self.aliases:
            return
        if existing is not None and existing != path:
            self.aliases[alias] = None
            return
        self.aliases[alias] = path

    def _module_parts(self, path: str) -> list[str]:
        source_path = PurePosixPath(path)
        parts = list(source_path.with_suffix("").parts)
        if parts and parts[-1] == "index":
            parts.pop()
        return parts

    def _normalize_parts(self, raw_parts: Sequence[str]) -> list[str]:
        parts: list[str] = []
        for part in raw_parts:
            if part in {"", "."}:
                continue
            if part == "..":
                if parts:
                    parts.pop()
                continue
            suffix = PurePosixPath(part).suffix
            parts.append(PurePosixPath(part).stem if suffix in self.EXTENSIONS else part)
        if parts and parts[-1] == "index":
            parts.pop()
        return parts


def _dependency_name(module: str) -> str:
    if module.startswith("node:"):
        return module
    parts = module.split("/")
    if module.startswith("@") and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]
