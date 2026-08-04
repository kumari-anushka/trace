from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import StrEnum

PYTHON_PARSER_VERSION = "1.0.0"


class PythonSymbolKind(StrEnum):
    CLASS = "class"
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    METHOD = "method"
    ASYNC_METHOD = "async_method"


@dataclass(frozen=True, slots=True)
class PythonSymbol:
    name: str
    qualified_name: str
    kind: PythonSymbolKind
    start_line: int
    end_line: int
    start_column: int
    end_column: int
    excerpt: str


@dataclass(frozen=True, slots=True)
class PythonImport:
    module: str | None
    imported_name: str | None
    alias: str | None
    level: int
    scope: str | None
    start_line: int
    end_line: int
    excerpt: str


@dataclass(frozen=True, slots=True)
class PythonParseFailure:
    message: str
    line: int | None
    column: int | None


@dataclass(frozen=True, slots=True)
class PythonParseResult:
    symbols: tuple[PythonSymbol, ...]
    imports: tuple[PythonImport, ...]
    failure: PythonParseFailure | None = None


class PythonParser:
    """Extract declarations and syntactic imports without inferring runtime calls."""

    def parse(self, *, path: str, content: str) -> PythonParseResult:
        try:
            tree = ast.parse(content, filename=path, type_comments=True)
        except SyntaxError as error:
            return PythonParseResult(
                symbols=(),
                imports=(),
                failure=PythonParseFailure(
                    message=error.msg,
                    line=error.lineno,
                    column=error.offset,
                ),
            )
        except (ValueError, RecursionError) as error:
            return PythonParseResult(
                symbols=(),
                imports=(),
                failure=PythonParseFailure(message=str(error), line=None, column=None),
            )

        visitor = _PythonVisitor(content)
        visitor.visit(tree)
        return PythonParseResult(
            symbols=tuple(visitor.symbols),
            imports=tuple(visitor.imports),
        )


class _PythonVisitor(ast.NodeVisitor):
    def __init__(self, content: str) -> None:
        self.lines = content.splitlines()
        self.scopes: list[tuple[str, str]] = []
        self.symbols: list[PythonSymbol] = []
        self.imports: list[PythonImport] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add_symbol(node, PythonSymbolKind.CLASS)
        self.scopes.append(("class", node.name))
        self.generic_visit(node)
        self.scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        kind = (
            PythonSymbolKind.METHOD
            if self.scopes and self.scopes[-1][0] == "class"
            else PythonSymbolKind.FUNCTION
        )
        self._visit_function(node, kind)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        kind = (
            PythonSymbolKind.ASYNC_METHOD
            if self.scopes and self.scopes[-1][0] == "class"
            else PythonSymbolKind.ASYNC_FUNCTION
        )
        self._visit_function(node, kind)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(
                PythonImport(
                    module=alias.name,
                    imported_name=None,
                    alias=alias.asname,
                    level=0,
                    scope=self._scope_name(),
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    excerpt=self._excerpt(node.lineno, node.end_lineno),
                )
            )

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            self.imports.append(
                PythonImport(
                    module=node.module,
                    imported_name=alias.name,
                    alias=alias.asname,
                    level=node.level,
                    scope=self._scope_name(),
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    excerpt=self._excerpt(node.lineno, node.end_lineno),
                )
            )

    def _visit_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        kind: PythonSymbolKind,
    ) -> None:
        self._add_symbol(node, kind)
        self.scopes.append(("function", node.name))
        self.generic_visit(node)
        self.scopes.pop()

    def _add_symbol(
        self,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        kind: PythonSymbolKind,
    ) -> None:
        start_line = min(
            (decorator.lineno for decorator in node.decorator_list),
            default=node.lineno,
        )
        qualified_name = ".".join([*(name for _, name in self.scopes), node.name])
        self.symbols.append(
            PythonSymbol(
                name=node.name,
                qualified_name=qualified_name,
                kind=kind,
                start_line=start_line,
                end_line=node.end_lineno or node.lineno,
                start_column=node.col_offset,
                end_column=node.end_col_offset or node.col_offset,
                excerpt=self._excerpt(node.lineno, node.lineno),
            )
        )

    def _scope_name(self) -> str | None:
        if not self.scopes:
            return None
        return ".".join(name for _, name in self.scopes)

    def _excerpt(self, start_line: int, end_line: int | None) -> str:
        bounded_end = min(end_line or start_line, start_line + 5)
        return "\n".join(self.lines[start_line - 1 : bounded_end])[:1000]
