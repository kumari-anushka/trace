from uuid import UUID, uuid4

import pytest

from src.graph.javascript import JavaScriptGraphBuilder, JavaScriptSourceInput
from src.graph.models import EvidenceType, RelationshipType

from .fakes import MemoryGraphRepository


class MemoryJavaScriptSourceReader:
    def __init__(self, files: list[JavaScriptSourceInput]) -> None:
        self.files = files

    async def list_javascript_sources(
        self, repository_version_id: UUID
    ) -> list[JavaScriptSourceInput]:
        return self.files


def source(path: str, content: str) -> JavaScriptSourceInput:
    language = "TypeScript" if path.endswith((".ts", ".tsx")) else "JavaScript"
    return JavaScriptSourceInput(
        id=uuid4(),
        path=path,
        blob_sha="b" * 40,
        file_kind="source",
        language=language,
        size=len(content.encode()),
        content=content,
    )


@pytest.mark.asyncio
async def test_builds_idempotent_javascript_typescript_graph() -> None:
    repository_id = uuid4()
    repository_version_id = uuid4()
    graph_repository = MemoryGraphRepository()
    builder = JavaScriptGraphBuilder(
        graph_repository=graph_repository,
        source_reader=MemoryJavaScriptSourceReader(
            [
                source(
                    "frontend/src/App.tsx",
                    """import React from "react";
import { Button } from "./Button";
export default function App() { return <Button />; }
export function useTrace() { return true; }
""",
                ),
                source(
                    "frontend/src/Button.tsx",
                    "export const Button = () => <button />;\n",
                ),
                source("frontend/src/broken.ts", "export function broken( {\n"),
            ]
        ),
    )

    first = await builder.build(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
    )
    second = await builder.build(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
    )

    assert first == second
    assert first.files == 3
    assert first.parsed_files == 2
    assert first.failed_files == 1
    assert first.symbols == 3
    assert first.imports == 2
    assert first.exports == 3
    assert first.components == 2
    assert first.hooks == 1
    assert first.internal_imports == 1
    assert first.external_imports == 1
    assert first.unresolved_imports == 0
    assert first.failures[0].path == "frontend/src/broken.ts"
    assert len(graph_repository.nodes) == 7
    assert len(graph_repository.edges) == 5
    assert len(graph_repository.evidence) == 8
    assert {edge.relationship_type for edge in graph_repository.edges.values()} == {
        RelationshipType.DECLARES,
        RelationshipType.IMPORTS,
    }
    assert all(
        evidence.evidence_type == EvidenceType.SOURCE_SPAN
        for evidence in graph_repository.evidence.values()
    )
