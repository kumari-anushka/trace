from src.parsers.python import PythonParser, PythonSymbolKind


def test_extracts_symbols_imports_scopes_and_source_spans() -> None:
    result = PythonParser().parse(
        path="src/app/service.py",
        content="""import os
from app.helpers import tool as helper

class Service:
    @trace
    async def run(self):
        from .local import execute
        return helper()

def boot():
    return Service()
""",
    )

    assert result.failure is None
    assert [symbol.qualified_name for symbol in result.symbols] == [
        "Service",
        "Service.run",
        "boot",
    ]
    assert [symbol.kind for symbol in result.symbols] == [
        PythonSymbolKind.CLASS,
        PythonSymbolKind.ASYNC_METHOD,
        PythonSymbolKind.FUNCTION,
    ]
    assert result.symbols[1].start_line == 5
    assert result.symbols[1].excerpt == "    async def run(self):"
    assert [(item.module, item.imported_name, item.scope) for item in result.imports] == [
        ("os", None, None),
        ("app.helpers", "tool", None),
        ("local", "execute", "Service.run"),
    ]
    assert result.imports[2].level == 1
    assert result.imports[2].start_line == 7


def test_syntax_failure_degrades_to_empty_structured_result() -> None:
    result = PythonParser().parse(path="broken.py", content="def broken(:\n")

    assert result.symbols == ()
    assert result.imports == ()
    assert result.failure is not None
    assert result.failure.line == 1
    assert result.failure.message
