from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.graph.models import EntityType, KnowledgeKind, RelationshipType
from src.graph.repository import GraphNodeInput
from src.semantic.subsystems import (
    CochangeInput,
    DeterministicSubsystemDiscoverer,
    SubsystemCandidateStore,
    SubsystemDiscoveryBuilder,
    SubsystemDiscoveryInput,
    SubsystemFileInput,
    SubsystemSignalReader,
)
from tests.graph.fakes import MemoryGraphRepository


def _file(
    path: str,
    *,
    community: str | None = None,
    embedding: tuple[float, ...] | None = None,
) -> SubsystemFileInput:
    return SubsystemFileInput(
        node_id=uuid4(),
        canonical_key=f"file:{path}",
        path=path,
        community_key=community,
        embedding=embedding,
    )


def test_discovers_separate_candidates_from_agreeing_structural_signals() -> None:
    repository_id = uuid4()
    repository_version_id = uuid4()
    api_files = (
        _file("backend/api/routes.py", community="community:api"),
        _file("backend/api/schemas.py", community="community:api"),
    )
    ui_files = (
        _file("frontend/components/Button.tsx", community="community:ui"),
        _file("frontend/components/Modal.tsx", community="community:ui"),
    )
    unrelated = _file("scripts/release.py", community="community:release")

    candidates = DeterministicSubsystemDiscoverer().discover(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        data=SubsystemDiscoveryInput(files=(*api_files, *ui_files, unrelated)),
    )

    assert len(candidates) == 2
    assert [{member.path for member in candidate.members} for candidate in candidates] == [
        {member.path for member in api_files},
        {member.path for member in ui_files},
    ]
    assert all("directory" in candidate.signals for candidate in candidates)
    assert all("graph_community" in candidate.signals for candidate in candidates)
    assert all(candidate.confidence >= 0.55 for candidate in candidates)


def test_combines_cochange_and_embedding_signals_across_directories() -> None:
    repository_id = uuid4()
    repository_version_id = uuid4()
    worker = _file("backend/jobs/runner.py", embedding=(1.0, 0.0))
    queue = _file("infra/redis/consumer.py", embedding=(0.9, 0.1))

    candidates = DeterministicSubsystemDiscoverer().discover(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        data=SubsystemDiscoveryInput(
            files=(worker, queue),
            cochanges=(
                CochangeInput(
                    left_node_id=worker.node_id,
                    right_node_id=queue.node_id,
                    count=2,
                ),
            ),
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].signals == ("cochange", "embedding")


@pytest.mark.asyncio
async def test_builder_persists_candidate_memberships_and_node_evidence() -> None:
    repository_id = uuid4()
    repository_version_id = uuid4()
    members = (
        _file("backend/api/routes.py", community="community:api"),
        _file("backend/api/schemas.py", community="community:api"),
    )
    graph_repository = MemoryGraphRepository()
    for member in members:
        node = await graph_repository.upsert_node(
            GraphNodeInput(
                repository_id=repository_id,
                repository_version_id=repository_version_id,
                entity_type=EntityType.FILE,
                canonical_key=member.canonical_key,
                name=member.path,
                provenance={"test": True},
            )
        )
        object.__setattr__(member, "node_id", node.id)

    signal_reader = AsyncMock(spec=SubsystemSignalReader)
    signal_reader.read.return_value = SubsystemDiscoveryInput(files=members)
    candidate_store = AsyncMock(spec=SubsystemCandidateStore)
    candidate_store.prune_candidates.return_value = 1
    builder = SubsystemDiscoveryBuilder(
        graph_repository=graph_repository,
        signal_reader=signal_reader,
        candidate_store=candidate_store,
    )

    summary = await builder.build(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
    )

    assert summary.candidates == 1
    assert summary.memberships == 2
    assert summary.evidence == 2
    assert summary.stale_candidates == 1
    subsystem_nodes = [
        node for node in graph_repository.nodes.values() if node.entity_type == EntityType.SUBSYSTEM
    ]
    assert len(subsystem_nodes) == 1
    assert subsystem_nodes[0].knowledge_kind == KnowledgeKind.INFERRED
    assert subsystem_nodes[0].details["status"] == "candidate"
    memberships = [
        edge
        for edge in graph_repository.edges.values()
        if edge.relationship_type == RelationshipType.PART_OF_SUBSYSTEM
    ]
    assert len(memberships) == 2
    assert all(edge.knowledge_kind == KnowledgeKind.INFERRED for edge in memberships)
    assert {evidence.target_node_id for evidence in graph_repository.evidence.values()} == {
        subsystem_nodes[0].id
    }
