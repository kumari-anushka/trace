import pytest

from src.parsers.javascript import (
    JavaScriptImportKind,
    JavaScriptParser,
    JavaScriptSymbolKind,
)


def test_extracts_typescript_imports_exports_symbols_components_and_hooks() -> None:
    result = JavaScriptParser().parse(
        path="frontend/src/App.tsx",
        content="""import React, { type FC, useState as state } from "react";
import { helper } from "./helper";
export { shared as renamed } from "./shared";

export interface Props { label: string }
export default function App() { return <main />; }
export const Button: FC<Props> = (props) => <button>{props.label}</button>;
export function useTrace() { state(1); }
const version = 1;
class Legacy extends React.Component { render() { return <div />; } }
""",
    )

    assert result.failure is None
    symbols = {symbol.qualified_name: symbol for symbol in result.symbols}
    assert set(symbols) == {
        "Props",
        "App",
        "Button",
        "useTrace",
        "version",
        "Legacy",
        "Legacy.render",
    }
    assert symbols["Props"].kind is JavaScriptSymbolKind.INTERFACE
    assert symbols["App"].is_component is True
    assert symbols["App"].default_export is True
    assert symbols["Button"].is_component is True
    assert symbols["Button"].exported is True
    assert symbols["useTrace"].is_hook is True
    assert symbols["Legacy"].is_component is True
    assert symbols["version"].kind is JavaScriptSymbolKind.VARIABLE
    assert symbols["Legacy.render"].exported is False

    imports = [
        (item.module, item.imported_name, item.local_name, item.kind, item.type_only)
        for item in result.imports
    ]
    assert ("react", "default", "React", JavaScriptImportKind.ES_IMPORT, False) in imports
    assert ("react", "FC", "FC", JavaScriptImportKind.ES_IMPORT, True) in imports
    assert ("react", "useState", "state", JavaScriptImportKind.ES_IMPORT, False) in imports
    assert (
        "./shared",
        "shared",
        "renamed",
        JavaScriptImportKind.RE_EXPORT,
        False,
    ) in imports
    assert any(item.name == "renamed" and item.source == "./shared" for item in result.exports)


def test_extracts_commonjs_and_dynamic_imports() -> None:
    result = JavaScriptParser().parse(
        path="src/index.js",
        content="""const fs = require("node:fs");
const lazy = import("./lazy.js");
exports.run = run;
module.exports.value = 1;
""",
    )

    assert result.failure is None
    assert [(item.module, item.kind) for item in result.imports] == [
        ("node:fs", JavaScriptImportKind.REQUIRE),
        ("./lazy.js", JavaScriptImportKind.DYNAMIC_IMPORT),
    ]
    assert {item.name for item in result.exports} == {"run", "value"}


def test_extracts_large_tsx_tree_without_recursive_descendant_materialization() -> None:
    elements = "\n".join(f"<span>Stage {index}</span>" for index in range(600))

    result = JavaScriptParser().parse(
        path="src/LargePage.tsx",
        content=(f"export function LargePage() {{\n  return <main>\n{elements}\n  </main>;\n}}\n"),
    )

    assert result.failure is None
    assert [symbol.qualified_name for symbol in result.symbols] == ["LargePage"]
    assert result.symbols[0].is_component is True
    assert [exported.name for exported in result.exports] == ["LargePage"]


@pytest.mark.parametrize("path", ["broken.ts", "broken.jsx"])
def test_syntax_failure_is_structured(path: str) -> None:
    result = JavaScriptParser().parse(path=path, content="export function broken( {\n")

    assert result.symbols == ()
    assert result.imports == ()
    assert result.exports == ()
    assert result.failure is not None
    assert result.failure.line == 1
