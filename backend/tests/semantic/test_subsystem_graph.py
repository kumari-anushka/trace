from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest

from src.semantic.subsystem_graph import (
    DeterministicSubsystemGraphAnalyzer,
    FileImportInput,
    SubsystemGraphBuilder,
    SubsystemGraphInput,
    SubsystemGraphNodeInput,
    SubsystemMembershipInput,
)
from tests.graph.fakes import MemoryGraphRepository


class StaticSubsystemGraphReader:
    def __init__(self, data: SubsystemGraphInput) -> None:
        self.data = data

    async def read(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> SubsystemGraphInput:
        return self.data


class MemorySubsystemGraphStore:
    def __init__(self) -> None:
        self.retained_pairs: tuple[tuple[UUID, UUID], ...] = ()

    async def prune_dependencies(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        retained_pairs: Sequence[tuple[UUID, UUID]],
    ) -> int:
        self.retained_pairs = tuple(retained_pairs)
        return 0


def _input() -> SubsystemGraphInput:
    api_id = uuid4()
    data_id = uuid4()
    api_file = uuid4()
    api_schema = uuid4()
    data_file = uuid4()
    return SubsystemGraphInput(
        subsystems=(
            SubsystemGraphNodeInput(
                node_id=api_id,
                canonical_key="subsystem:api",
                name="API",
                status="confirmed",
                confidence=0.9,
            ),
            SubsystemGraphNodeInput(
                node_id=data_id,
                canonical_key="subsystem:data",
                name="Data",
                status="candidate",
                confidence=0.7,
            ),
        ),
        memberships=(
            SubsystemMembershipInput(api_file, api_id),
            SubsystemMembershipInput(api_schema, api_id),
            SubsystemMembershipInput(data_file, data_id),
        ),
        imports=(
            FileImportInput(uuid4(), api_file, api_schema, "api/routes.py", "api/schema.py"),
            FileImportInput(uuid4(), api_file, data_file, "api/routes.py", "data/store.py"),
            FileImportInput(uuid4(), api_schema, data_file, "api/schema.py", "data/store.py"),
        ),
    )


def test_analyzer_collapses_cross_subsystem_imports_by_direction() -> None:
    dependencies = DeterministicSubsystemGraphAnalyzer().analyze(_input())

    assert len(dependencies) == 1
    assert dependencies[0].source.name == "API"
    assert dependencies[0].target.name == "Data"
    assert len(dependencies[0].imports) == 2


@pytest.mark.asyncio
async def test_builder_persists_idempotent_dependency_with_graph_path_evidence() -> None:
    repository_id = uuid4()
    repository_version_id = uuid4()
    data = _input()
    graph_repository = MemoryGraphRepository()
    store = MemorySubsystemGraphStore()
    builder = SubsystemGraphBuilder(
        graph_repository=graph_repository,
        reader=StaticSubsystemGraphReader(data),
        store=store,
    )

    for _ in range(2):
        summary = await builder.build(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
        )

    assert summary.dependencies == 1
    assert summary.evidence == 2
    assert len(graph_repository.edges) == 1
    assert len(graph_repository.evidence) == 2
    assert store.retained_pairs == ((data.subsystems[0].node_id, data.subsystems[1].node_id),)
