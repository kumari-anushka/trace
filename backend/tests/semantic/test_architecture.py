from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from src.graph.models import EntityType
from src.semantic.architecture import (
    ArchitectureBuilder,
    ArchitectureDependencyInput,
    ArchitectureFileInput,
    ArchitectureInput,
    ArchitectureSubsystemInput,
    ArchitectureSymbolInput,
    DeterministicArchitectureAnalyzer,
)
from tests.graph.fakes import MemoryGraphRepository


class StaticArchitectureReader:
    def __init__(self, data: ArchitectureInput) -> None:
        self.data = data

    async def read(self, *, repository_id: UUID, repository_version_id: UUID) -> ArchitectureInput:
        return self.data


class MemoryArchitectureStore:
    def __init__(self) -> None:
        self.retained_targets: tuple[UUID, ...] = ()

    async def prune_summary_edges(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        summary_node_id: UUID,
        retained_target_node_ids: Sequence[UUID],
    ) -> int:
        self.retained_targets = tuple(retained_target_node_ids)
        return 0


def _architecture_input() -> ArchitectureInput:
    manifest_id = uuid4()
    cli_id = uuid4()
    main_id = uuid4()
    helper_id = uuid4()
    dependency_id = uuid4()
    stdlib_id = uuid4()
    return ArchitectureInput(
        files=(
            ArchitectureFileInput(
                node_id=manifest_id,
                canonical_key="file:package.json",
                path="package.json",
                language="JSON",
                content='{"bin": {"trace": "src/cli.ts"}}',
                source_url="https://example.test/package.json",
            ),
            ArchitectureFileInput(
                node_id=cli_id,
                canonical_key="file:src/cli.ts",
                path="src/cli.ts",
                language="TypeScript",
                content="export function run() {}",
                source_url="https://example.test/src/cli.ts",
                degree_centrality=0.4,
            ),
            ArchitectureFileInput(
                node_id=main_id,
                canonical_key="file:src/main.py",
                path="src/main.py",
                language="Python",
                content='def main():\n    pass\n\nif __name__ == "__main__":\n    main()\n',
                source_url="https://example.test/src/main.py",
                declarations=(ArchitectureSymbolInput(name="main", start_line=1),),
                degree_centrality=0.9,
            ),
            ArchitectureFileInput(
                node_id=helper_id,
                canonical_key="file:src/app.py",
                path="src/app.py",
                language="Python",
                content="def helper():\n    pass\n",
                source_url="https://example.test/src/app.py",
                degree_centrality=0.2,
            ),
        ),
        dependencies=(
            ArchitectureDependencyInput(
                node_id=dependency_id,
                canonical_key="dependency:fastapi",
                name="fastapi",
                ecosystem="python",
                dependency_kind="package",
                importer_node_ids=(main_id, helper_id),
                import_edge_ids=(uuid4(), uuid4()),
            ),
            ArchitectureDependencyInput(
                node_id=stdlib_id,
                canonical_key="dependency:os",
                name="os",
                ecosystem="python",
                dependency_kind="standard_library",
                importer_node_ids=(main_id,),
                import_edge_ids=(uuid4(),),
            ),
        ),
        subsystems=(
            ArchitectureSubsystemInput(
                node_id=uuid4(),
                canonical_key="subsystem:api",
                name="API",
                status="confirmed",
                confidence=0.9,
                member_count=3,
            ),
            ArchitectureSubsystemInput(
                node_id=uuid4(),
                canonical_key="subsystem:worker",
                name="Worker candidate",
                status="candidate",
                confidence=0.7,
                member_count=2,
            ),
        ),
    )


def test_analyzer_detects_grounded_entry_points_and_major_dependencies() -> None:
    facts = DeterministicArchitectureAnalyzer().analyze(_architecture_input())

    assert [item.path for item in facts.entry_points] == ["src/cli.ts", "src/main.py"]
    assert facts.entry_points[0].signals == (
        "conventional_entry_filename",
        "manifest_entry",
    )
    assert "python_main_guard" in facts.entry_points[1].signals
    assert [item.name for item in facts.major_dependencies] == ["fastapi"]
    assert [item.name for item in facts.confirmed_subsystems] == ["API"]
    assert [item.path for item in facts.central_files] == [
        "src/main.py",
        "src/cli.ts",
        "src/app.py",
    ]


@pytest.mark.asyncio
async def test_builder_persists_one_idempotent_evidence_backed_summary() -> None:
    repository_id = uuid4()
    repository_version_id = uuid4()
    data = _architecture_input()
    graph_repository = MemoryGraphRepository()
    store = MemoryArchitectureStore()
    builder = ArchitectureBuilder(
        graph_repository=graph_repository,
        reader=StaticArchitectureReader(data),
        store=store,
    )

    for _ in range(2):
        summary = await builder.build(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
        )

    architecture_nodes = [
        node
        for node in graph_repository.nodes.values()
        if node.entity_type == EntityType.ARCHITECTURE_SUMMARY
    ]
    assert len(architecture_nodes) == 1
    assert summary.entry_points == 2
    assert summary.major_external_dependencies == 1
    assert summary.confirmed_subsystems == 1
    assert summary.derived_edges == 4
    assert summary.evidence == 5
    assert len(graph_repository.edges) == 4
    assert len(graph_repository.evidence) == 5
    assert set(store.retained_targets) == {
        *(
            item.file_node_id
            for item in DeterministicArchitectureAnalyzer().analyze(data).entry_points
        ),
        data.dependencies[0].node_id,
        data.subsystems[0].node_id,
    }
