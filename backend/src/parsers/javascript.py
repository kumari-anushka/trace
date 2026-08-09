from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import PurePosixPath

import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

JAVASCRIPT_PARSER_VERSION = "1.0.0"
_HOOK_NAME = re.compile(r"^use(?:[A-Z0-9].*)$")
_DECLARATION_KINDS = {
    "class_declaration": "class",
    "abstract_class_declaration": "class",
    "function_declaration": "function",
    "generator_function_declaration": "generator_function",
    "interface_declaration": "interface",
    "type_alias_declaration": "type_alias",
    "enum_declaration": "enum",
}


class JavaScriptSymbolKind(StrEnum):
    CLASS = "class"
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    GENERATOR_FUNCTION = "generator_function"
    METHOD = "method"
    ARROW_FUNCTION = "arrow_function"
    FUNCTION_EXPRESSION = "function_expression"
    INTERFACE = "interface"
    TYPE_ALIAS = "type_alias"
    ENUM = "enum"
    VARIABLE = "variable"


class JavaScriptImportKind(StrEnum):
    ES_IMPORT = "es_import"
    REQUIRE = "require"
    DYNAMIC_IMPORT = "dynamic_import"
    RE_EXPORT = "re_export"


@dataclass(frozen=True, slots=True)
class JavaScriptSymbol:
    name: str
    qualified_name: str
    kind: JavaScriptSymbolKind
    start_line: int
    end_line: int
    start_column: int
    end_column: int
    excerpt: str
    exported: bool = False
    default_export: bool = False
    is_component: bool = False
    is_hook: bool = False


@dataclass(frozen=True, slots=True)
class JavaScriptImport:
    module: str
    imported_name: str | None
    local_name: str | None
    kind: JavaScriptImportKind
    type_only: bool
    scope: str | None
    start_line: int
    end_line: int
    excerpt: str


@dataclass(frozen=True, slots=True)
class JavaScriptExport:
    name: str
    local_name: str | None
    source: str | None
    default: bool
    type_only: bool
    start_line: int
    end_line: int
    excerpt: str


@dataclass(frozen=True, slots=True)
class JavaScriptParseFailure:
    message: str
    line: int | None
    column: int | None


@dataclass(frozen=True, slots=True)
class JavaScriptParseResult:
    symbols: tuple[JavaScriptSymbol, ...]
    imports: tuple[JavaScriptImport, ...]
    exports: tuple[JavaScriptExport, ...]
    failure: JavaScriptParseFailure | None = None


class JavaScriptParser:
    """Tree-sitter parser for JavaScript, JSX, TypeScript, and TSX source."""

    def __init__(self) -> None:
        self.parsers = {
            ".js": Parser(Language(tree_sitter_javascript.language())),
            ".jsx": Parser(Language(tree_sitter_javascript.language())),
            ".mjs": Parser(Language(tree_sitter_javascript.language())),
            ".cjs": Parser(Language(tree_sitter_javascript.language())),
            ".ts": Parser(Language(tree_sitter_typescript.language_typescript())),
            ".tsx": Parser(Language(tree_sitter_typescript.language_tsx())),
        }

    def parse(self, *, path: str, content: str) -> JavaScriptParseResult:
        suffix = PurePosixPath(path).suffix.lower()
        parser = self.parsers.get(suffix)
        if parser is None:
            return JavaScriptParseResult(
                symbols=(),
                imports=(),
                exports=(),
                failure=JavaScriptParseFailure(
                    message=f"Unsupported JavaScript/TypeScript extension: {suffix}",
                    line=None,
                    column=None,
                ),
            )

        source = content.encode("utf-8")
        tree = parser.parse(source)
        if tree.root_node.has_error:
            error_node = _first_error(tree.root_node)
            return JavaScriptParseResult(
                symbols=(),
                imports=(),
                exports=(),
                failure=JavaScriptParseFailure(
                    message="Source contains a syntax error",
                    line=error_node.start_point.row + 1 if error_node else None,
                    column=error_node.start_point.column if error_node else None,
                ),
            )

        extractor = _JavaScriptExtractor(source)
        extractor.extract(tree.root_node)
        exported_names = {
            item.local_name: item.default
            for item in extractor.exports
            if item.local_name is not None and item.source is None
        }
        symbols = tuple(
            replace(
                symbol,
                exported=(symbol.qualified_name == symbol.name and symbol.name in exported_names),
                default_export=(
                    symbol.qualified_name == symbol.name and exported_names.get(symbol.name, False)
                ),
            )
            for symbol in extractor.symbols
        )
        return JavaScriptParseResult(
            symbols=symbols,
            imports=tuple(extractor.imports),
            exports=tuple(extractor.exports),
        )


class _JavaScriptExtractor:
    def __init__(self, source: bytes) -> None:
        self.source = source
        self.symbols: list[JavaScriptSymbol] = []
        self.imports: list[JavaScriptImport] = []
        self.exports: list[JavaScriptExport] = []

    def extract(self, root: Node) -> None:
        self._walk(root, ())

    def _walk(self, node: Node, scopes: tuple[str, ...]) -> None:
        if node.type in _DECLARATION_KINDS:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = self._text(name_node)
                kind = self._declaration_kind(node)
                self._add_symbol(node=node, name=name, scopes=scopes, kind=kind)
                child_scopes = (*scopes, name)
                for child in node.named_children:
                    self._walk(child, child_scopes)
                return

        if node.type in {"method_definition", "abstract_method_signature"}:
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = self._text(name_node)
                self._add_symbol(
                    node=node,
                    name=name,
                    scopes=scopes,
                    kind=JavaScriptSymbolKind.METHOD,
                )
                for child in node.named_children:
                    self._walk(child, (*scopes, name))
                return

        if node.type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")
            if (
                name_node is not None
                and name_node.type == "identifier"
                and not _inside_function(node)
            ):
                name = self._text(name_node)
                is_callable = value_node is not None and self._callable_value(value_node)
                if value_node is not None and value_node.type == "function_expression":
                    kind = JavaScriptSymbolKind.FUNCTION_EXPRESSION
                elif is_callable:
                    kind = JavaScriptSymbolKind.ARROW_FUNCTION
                else:
                    kind = JavaScriptSymbolKind.VARIABLE
                self._add_symbol(
                    node=node,
                    name=name,
                    scopes=scopes,
                    kind=kind,
                    component_node=value_node if is_callable else None,
                )
                if value_node is not None:
                    child_scopes = (*scopes, name) if is_callable else scopes
                    self._walk(value_node, child_scopes)
                return

        if node.type == "export_statement":
            self._extract_export_statement(node)
            if node.child_by_field_name("source") is not None:
                self._extract_re_export_imports(node, scopes)
        elif node.type == "assignment_expression":
            exported = self._commonjs_export(node)
            if exported is not None:
                self.exports.append(exported)

        if node.type == "import_statement":
            self._extract_import_statement(node, scopes)
        elif node.type == "call_expression":
            parsed_import = self._extract_call_import(node, scopes)
            if parsed_import is not None:
                self.imports.append(parsed_import)

        for child in node.named_children:
            self._walk(child, scopes)

    def _add_symbol(
        self,
        *,
        node: Node,
        name: str,
        scopes: tuple[str, ...],
        kind: JavaScriptSymbolKind,
        component_node: Node | None = None,
    ) -> None:
        qualified_name = ".".join((*scopes, name))
        candidate = component_node or node
        self.symbols.append(
            JavaScriptSymbol(
                name=name,
                qualified_name=qualified_name,
                kind=kind,
                start_line=node.start_point.row + 1,
                end_line=node.end_point.row + 1,
                start_column=node.start_point.column,
                end_column=node.end_point.column,
                excerpt=self._line_excerpt(node),
                is_component=(
                    name[:1].isupper()
                    and (
                        (
                            self._is_function_kind(kind)
                            and (
                                _contains_jsx(candidate)
                                or "React.createElement" in self._text(candidate)
                            )
                        )
                        or self._extends_react_component(node)
                    )
                ),
                is_hook=bool(_HOOK_NAME.match(name)) and self._is_function_kind(kind),
            )
        )

    def _extract_import_statement(self, node: Node, scopes: tuple[str, ...]) -> None:
        source_node = node.child_by_field_name("source")
        if source_node is None:
            return
        module = self._string_value(source_node)
        clause = next(
            (child for child in node.named_children if child.type == "import_clause"),
            None,
        )
        statement_type_only = self._text(node).lstrip().startswith("import type ")
        if clause is None:
            self.imports.append(
                self._import_record(
                    node=node,
                    module=module,
                    imported_name=None,
                    local_name=None,
                    kind=JavaScriptImportKind.ES_IMPORT,
                    type_only=statement_type_only,
                    scopes=scopes,
                )
            )
            return

        found = False
        for child in clause.named_children:
            if child.type == "identifier":
                found = True
                self.imports.append(
                    self._import_record(
                        node=node,
                        module=module,
                        imported_name="default",
                        local_name=self._text(child),
                        kind=JavaScriptImportKind.ES_IMPORT,
                        type_only=statement_type_only,
                        scopes=scopes,
                    )
                )
            elif child.type == "namespace_import":
                found = True
                local = next(iter(child.named_children), None)
                self.imports.append(
                    self._import_record(
                        node=node,
                        module=module,
                        imported_name="*",
                        local_name=self._text(local) if local else None,
                        kind=JavaScriptImportKind.ES_IMPORT,
                        type_only=statement_type_only,
                        scopes=scopes,
                    )
                )
            elif child.type == "named_imports":
                for specifier in child.named_children:
                    if specifier.type != "import_specifier":
                        continue
                    found = True
                    name_node = specifier.child_by_field_name("name")
                    alias_node = specifier.child_by_field_name("alias")
                    imported_name = self._text(name_node) if name_node else None
                    self.imports.append(
                        self._import_record(
                            node=specifier,
                            module=module,
                            imported_name=imported_name,
                            local_name=self._text(alias_node) if alias_node else imported_name,
                            kind=JavaScriptImportKind.ES_IMPORT,
                            type_only=(
                                statement_type_only
                                or self._text(specifier).lstrip().startswith("type ")
                            ),
                            scopes=scopes,
                        )
                    )
        if not found:
            self.imports.append(
                self._import_record(
                    node=node,
                    module=module,
                    imported_name=None,
                    local_name=None,
                    kind=JavaScriptImportKind.ES_IMPORT,
                    type_only=statement_type_only,
                    scopes=scopes,
                )
            )

    def _extract_export_statement(self, node: Node) -> None:
        source_node = node.child_by_field_name("source")
        source = self._string_value(source_node) if source_node else None
        is_default = any(child.type == "default" for child in node.children)
        declaration = node.child_by_field_name("declaration")
        if declaration is not None:
            names = self._declaration_names(declaration)
            for name in names:
                self.exports.append(
                    self._export_record(
                        node=node,
                        name="default" if is_default else name,
                        local_name=name,
                        source=source,
                        default=is_default,
                        type_only=declaration.type
                        in {"interface_declaration", "type_alias_declaration"},
                    )
                )
            return

        value = node.child_by_field_name("value")
        if value is not None:
            local_name = self._text(value)
            self.exports.append(
                self._export_record(
                    node=node,
                    name="default" if is_default else local_name,
                    local_name=local_name,
                    source=source,
                    default=is_default,
                )
            )
            return

        clause = next(
            (child for child in node.named_children if child.type == "export_clause"),
            None,
        )
        if clause is not None:
            for specifier in clause.named_children:
                if specifier.type != "export_specifier":
                    continue
                name_node = specifier.child_by_field_name("name")
                alias_node = specifier.child_by_field_name("alias")
                specifier_local_name = self._text(name_node) if name_node else None
                export_name = self._text(alias_node) if alias_node else specifier_local_name
                if export_name is not None:
                    self.exports.append(
                        self._export_record(
                            node=specifier,
                            name=export_name,
                            local_name=specifier_local_name,
                            source=source,
                            default=export_name == "default",
                            type_only=self._text(specifier).lstrip().startswith("type "),
                        )
                    )
            return

        namespace = next(
            (child for child in node.named_children if child.type == "namespace_export"),
            None,
        )
        name_node = next(iter(namespace.named_children), None) if namespace else None
        name = self._text(name_node) if name_node else "*"
        self.exports.append(
            self._export_record(
                node=node,
                name=name,
                local_name=None,
                source=source,
                default=False,
            )
        )

    def _extract_re_export_imports(self, node: Node, scopes: tuple[str, ...]) -> None:
        source_node = node.child_by_field_name("source")
        if source_node is None:
            return
        module = self._string_value(source_node)
        matching = [
            exported
            for exported in self.exports
            if exported.source == module
            and node.start_point.row + 1 <= exported.start_line <= node.end_point.row + 1
        ]
        if not matching:
            matching = [
                self._export_record(
                    node=node,
                    name="*",
                    local_name=None,
                    source=module,
                    default=False,
                )
            ]
        for exported in matching:
            self.imports.append(
                self._import_record(
                    node=node,
                    module=module,
                    imported_name=exported.local_name or exported.name,
                    local_name=exported.name,
                    kind=JavaScriptImportKind.RE_EXPORT,
                    type_only=exported.type_only,
                    scopes=scopes,
                )
            )

    def _extract_call_import(self, node: Node, scopes: tuple[str, ...]) -> JavaScriptImport | None:
        function = node.child_by_field_name("function")
        arguments = node.child_by_field_name("arguments")
        if function is None or arguments is None:
            return None
        function_name = self._text(function)
        if function_name not in {"require", "import"}:
            return None
        string_node = next(
            (child for child in arguments.named_children if child.type == "string"),
            None,
        )
        if string_node is None:
            return None
        return self._import_record(
            node=node,
            module=self._string_value(string_node),
            imported_name=None,
            local_name=None,
            kind=(
                JavaScriptImportKind.REQUIRE
                if function_name == "require"
                else JavaScriptImportKind.DYNAMIC_IMPORT
            ),
            type_only=False,
            scopes=scopes,
        )

    def _commonjs_export(self, node: Node) -> JavaScriptExport | None:
        left = node.child_by_field_name("left")
        if left is None:
            return None
        target = self._text(left)
        if target == "module.exports":
            name = "default"
            default = True
        elif target.startswith("module.exports."):
            name = target.removeprefix("module.exports.")
            default = False
        elif target.startswith("exports."):
            name = target.removeprefix("exports.")
            default = False
        else:
            return None
        return self._export_record(
            node=node,
            name=name,
            local_name=None,
            source=None,
            default=default,
        )

    def _declaration_names(self, declaration: Node) -> list[str]:
        name = declaration.child_by_field_name("name")
        if name is not None and name.type in {"identifier", "type_identifier"}:
            return [self._text(name)]
        return [
            self._text(name_node)
            for declarator in declaration.named_children
            if declarator.type == "variable_declarator"
            if (name_node := declarator.child_by_field_name("name")) is not None
            and name_node.type == "identifier"
        ]

    def _declaration_kind(self, node: Node) -> JavaScriptSymbolKind:
        value = _DECLARATION_KINDS[node.type]
        if value == "function" and self._text(node).lstrip().startswith("async "):
            return JavaScriptSymbolKind.ASYNC_FUNCTION
        return JavaScriptSymbolKind(value)

    def _callable_value(self, node: Node) -> bool:
        if node.type in {"arrow_function", "function_expression"}:
            return True
        if node.type != "call_expression":
            return False
        function = node.child_by_field_name("function")
        if function is None or self._text(function) not in {
            "memo",
            "forwardRef",
            "React.memo",
            "React.forwardRef",
        }:
            return False
        return _contains_node_type(node, {"arrow_function", "function_expression"})

    def _extends_react_component(self, node: Node) -> bool:
        if node.type not in {"class_declaration", "abstract_class_declaration"}:
            return False
        heritage = next(
            (child for child in node.named_children if child.type == "class_heritage"),
            None,
        )
        if heritage is None:
            return False
        text = self._text(heritage)
        return any(
            base in text
            for base in ("React.Component", "React.PureComponent", "Component", "PureComponent")
        )

    @staticmethod
    def _is_function_kind(kind: JavaScriptSymbolKind) -> bool:
        return kind in {
            JavaScriptSymbolKind.FUNCTION,
            JavaScriptSymbolKind.ASYNC_FUNCTION,
            JavaScriptSymbolKind.GENERATOR_FUNCTION,
            JavaScriptSymbolKind.ARROW_FUNCTION,
            JavaScriptSymbolKind.FUNCTION_EXPRESSION,
        }

    def _import_record(
        self,
        *,
        node: Node,
        module: str,
        imported_name: str | None,
        local_name: str | None,
        kind: JavaScriptImportKind,
        type_only: bool,
        scopes: tuple[str, ...],
    ) -> JavaScriptImport:
        return JavaScriptImport(
            module=module,
            imported_name=imported_name,
            local_name=local_name,
            kind=kind,
            type_only=type_only,
            scope=".".join(scopes) or None,
            start_line=node.start_point.row + 1,
            end_line=node.end_point.row + 1,
            excerpt=self._line_excerpt(node),
        )

    def _export_record(
        self,
        *,
        node: Node,
        name: str,
        local_name: str | None,
        source: str | None,
        default: bool,
        type_only: bool = False,
    ) -> JavaScriptExport:
        return JavaScriptExport(
            name=name,
            local_name=local_name,
            source=source,
            default=default,
            type_only=type_only,
            start_line=node.start_point.row + 1,
            end_line=node.end_point.row + 1,
            excerpt=self._line_excerpt(node),
        )

    def _text(self, node: Node) -> str:
        return self.source[node.start_byte : node.end_byte].decode("utf-8")

    def _string_value(self, node: Node) -> str:
        fragment = next(
            (child for child in node.named_children if child.type == "string_fragment"),
            None,
        )
        return self._text(fragment) if fragment else self._text(node).strip("'\"")

    def _line_excerpt(self, node: Node) -> str:
        lines = self.source[node.start_byte : node.end_byte].decode("utf-8").splitlines()
        return "\n".join(lines[:6])[:1000]


def _contains_jsx(node: Node) -> bool:
    return _contains_node_type(
        node,
        {"jsx_element", "jsx_self_closing_element", "jsx_fragment"},
    )


def _contains_node_type(node: Node, node_types: set[str]) -> bool:
    if node.type in node_types:
        return True
    return any(_contains_node_type(child, node_types) for child in node.named_children)


def _first_error(node: Node) -> Node | None:
    if node.is_error or node.is_missing:
        return node
    for child in node.children:
        error = _first_error(child)
        if error is not None:
            return error
    return None


def _inside_function(node: Node) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type in {
            "arrow_function",
            "function_declaration",
            "function_expression",
            "generator_function_declaration",
            "method_definition",
        }:
            return True
        if parent.type == "program":
            return False
        parent = parent.parent
    return False
