from uuid import UUID, uuid4

import pytest

from src.graph.models import EvidenceType, RelationshipType
from src.graph.python import PythonGraphBuilder, PythonSourceInput

from .fakes import MemoryGraphRepository


class MemoryPythonSourceReader:
    def __init__(self, files: list[PythonSourceInput]) -> None:
        self.files = files

    async def list_python_sources(self, repository_version_id: UUID) -> list[PythonSourceInput]:
        return self.files


def source(path: str, content: str) -> PythonSourceInput:
    return PythonSourceInput(
        id=uuid4(),
        path=path,
        blob_sha="a" * 40,
        file_kind="source",
        size=len(content.encode()),
        content=content,
    )


@pytest.mark.asyncio
async def test_builds_idempotent_python_declaration_and_import_graph() -> None:
    repository_id = uuid4()
    repository_version_id = uuid4()
    graph_repository = MemoryGraphRepository()
    builder = PythonGraphBuilder(
        graph_repository=graph_repository,
        source_reader=MemoryPythonSourceReader(
            [
                source(
                    "backend/src/app/main.py",
                    """import os
from app.helpers import run
from .local import execute

def boot():
    return run()
""",
                ),
                source("backend/src/app/helpers.py", "def run():\n    return True\n"),
                source("backend/src/app/local.py", "VALUE = 1\n"),
                source("backend/src/app/broken.py", "def broken(:\n"),
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
    assert first.files == 4
    assert first.parsed_files == 3
    assert first.failed_files == 1
    assert first.symbols == 2
    assert first.imports == 3
    assert first.internal_imports == 2
    assert first.external_imports == 1
    assert first.unresolved_imports == 0
    assert first.failures[0].path == "backend/src/app/broken.py"
    assert len(graph_repository.nodes) == 7
    assert len(graph_repository.edges) == 5
    assert len(graph_repository.evidence) == 5
    assert {edge.relationship_type for edge in graph_repository.edges.values()} == {
        RelationshipType.DECLARES,
        RelationshipType.IMPORTS,
    }
    assert all(
        evidence.evidence_type == EvidenceType.SOURCE_SPAN
        for evidence in graph_repository.evidence.values()
    )
    assert all(evidence.start_line is not None for evidence in graph_repository.evidence.values())
