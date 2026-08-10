from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from src.graph.models import (
    EntityType,
    GraphEdge,
    GraphNode,
    KnowledgeKind,
    RelationshipType,
)
from src.graph.repository import GraphMetricInput
from src.intelligence.historical import (
    CONTRIBUTOR_SCORE_WEIGHTS,
    DeterministicHistoricalIntelligenceAnalyzer,
    HistoricalIntelligenceBuilder,
    HistoricalIntelligenceInput,
    HistoricalIntelligenceSummary,
)
from tests.graph.fakes import MemoryGraphRepository

REPOSITORY_ID = uuid4()
VERSION_ID = uuid4()


def node(
    entity_type: EntityType,
    name: str,
    *,
    description: str | None = None,
    details: dict[str, object] | None = None,
    repository_version_id: UUID | None = VERSION_ID,
) -> GraphNode:
    item = GraphNode(
        id=uuid4(),
        repository_id=REPOSITORY_ID,
        repository_version_id=repository_version_id,
        entity_type=entity_type.value,
        canonical_key=f"{entity_type.value}:{name}:{uuid4()}",
        name=name,
        description=description,
        knowledge_kind=KnowledgeKind.DETERMINISTIC.value,
        confidence=1.0,
        provenance={"kind": "test"},
        details=details or {},
        ontology_version="1.0",
    )
    return item


def edge(source: GraphNode, target: GraphNode, relationship: RelationshipType) -> GraphEdge:
    return GraphEdge(
        id=uuid4(),
        repository_id=REPOSITORY_ID,
        repository_version_id=VERSION_ID,
        source_node_id=source.id,
        target_node_id=target.id,
        relationship_type=relationship.value,
        knowledge_kind=KnowledgeKind.DETERMINISTIC.value,
        confidence=1.0,
        provenance={"kind": "test"},
        details={},
        ontology_version="1.0",
    )


def test_confirms_only_an_implemented_decision_with_context_and_affected_files() -> None:
    issue = node(
        EntityType.ISSUE,
        "#12 Database timeouts",
        description="The request path blocks while waiting for a database connection.",
        repository_version_id=None,
    )
    pull_request = node(
        EntityType.PULL_REQUEST,
        "#18 Adopt a bounded connection pool",
        description=(
            "Use a bounded pool and fail fast.\n\n"
            "## Alternatives considered\n- Keep unbounded connections\n- Add retries only"
        ),
        details={
            "merged_at": "2026-08-01T00:00:00+00:00",
            "html_url": "https://github.test/pull/18",
        },
        repository_version_id=None,
    )
    file = node(EntityType.FILE, "pool.py", details={"path": "src/pool.py"})
    subsystem = node(EntityType.SUBSYSTEM, "Database access")
    data = HistoricalIntelligenceInput(
        nodes=(issue, pull_request, file, subsystem),
        edges=(
            edge(pull_request, issue, RelationshipType.RESOLVES),
            edge(pull_request, file, RelationshipType.MODIFIES),
            edge(file, subsystem, RelationshipType.PART_OF_SUBSYSTEM),
        ),
    )

    result = DeterministicHistoricalIntelligenceAnalyzer().analyze(data)

    assert len(result.decisions) == 1
    decision = result.decisions[0]
    assert decision.status == "confirmed"
    assert decision.context.startswith("The request path blocks")
    assert decision.selected_choice == "Adopt a bounded connection pool"
    assert decision.alternatives == ("Keep unbounded connections", "Add retries only")
    assert decision.affected_files == (file,)
    assert decision.affected_subsystems == (subsystem,)
    assert decision.confidence >= 0.8


def test_keeps_a_merged_change_without_context_as_insufficient_evidence() -> None:
    pull_request = node(
        EntityType.PULL_REQUEST,
        "#20 Refactor cache",
        details={"merged_at": "2026-08-01T00:00:00+00:00"},
        repository_version_id=None,
    )
    file = node(EntityType.FILE, "cache.py", details={"path": "src/cache.py"})

    result = DeterministicHistoricalIntelligenceAnalyzer().analyze(
        HistoricalIntelligenceInput(
            nodes=(pull_request, file),
            edges=(edge(pull_request, file, RelationshipType.MODIFIES),),
        )
    )

    assert len(result.decisions) == 1
    assert result.decisions[0].status == "insufficient_evidence"
    assert result.decisions[0].confidence < 0.8


def test_contributor_score_is_explainable_and_recency_uses_repository_history() -> None:
    latest = datetime(2026, 8, 1, tzinfo=UTC)
    alice = node(EntityType.PERSON, "alice", repository_version_id=None)
    bob = node(EntityType.PERSON, "bob", repository_version_id=None)
    alice_pr = node(
        EntityType.PULL_REQUEST,
        "#1 Pool",
        details={"merged_at": latest.isoformat()},
        repository_version_id=None,
    )
    bob_commit = node(
        EntityType.COMMIT,
        "abc123 Old change",
        details={"git_author_date": (latest - timedelta(days=180)).isoformat()},
        repository_version_id=None,
    )
    file = node(EntityType.FILE, "pool.py", details={"path": "src/pool.py"})
    subsystem = node(EntityType.SUBSYSTEM, "Database access")
    data = HistoricalIntelligenceInput(
        nodes=(alice, bob, alice_pr, bob_commit, file, subsystem),
        edges=(
            edge(alice, alice_pr, RelationshipType.AUTHORED),
            edge(alice_pr, file, RelationshipType.MODIFIES),
            edge(bob, bob_commit, RelationshipType.AUTHORED),
            edge(bob_commit, file, RelationshipType.MODIFIES),
            edge(file, subsystem, RelationshipType.PART_OF_SUBSYSTEM),
        ),
    )

    contributors = DeterministicHistoricalIntelligenceAnalyzer().analyze(data).contributors

    by_name = {item.person.name: item for item in contributors}
    assert set(by_name) == {"alice", "bob"}
    assert by_name["alice"].recency == pytest.approx(1.0)
    assert by_name["bob"].recency == pytest.approx(0.5)
    assert by_name["alice"].active_subsystems == ((subsystem, 1),)
    assert by_name["alice"].score == pytest.approx(
        CONTRIBUTOR_SCORE_WEIGHTS["authored_pull_requests"]
        + CONTRIBUTOR_SCORE_WEIGHTS["subsystem_files"]
        + CONTRIBUTOR_SCORE_WEIGHTS["recency"]
    )


class MemoryIntelligenceStore:
    def __init__(self) -> None:
        self.metrics: tuple[GraphMetricInput, ...] = ()
        self.retained: tuple[str, ...] = ()

    async def prune_decisions(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        retained_canonical_keys: Sequence[str],
    ) -> int:
        self.retained = tuple(retained_canonical_keys)
        return 0

    async def replace_metrics(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        algorithm_version: str,
        metrics: Sequence[GraphMetricInput],
    ) -> int:
        self.metrics = tuple(metrics)
        return len(metrics)


class MemoryReader:
    def __init__(self, data: HistoricalIntelligenceInput) -> None:
        self.data = data

    async def read(
        self, *, repository_id: UUID, repository_version_id: UUID
    ) -> HistoricalIntelligenceInput:
        return self.data


@pytest.mark.asyncio
async def test_builder_persists_decision_evidence_and_contributor_metrics() -> None:
    person = node(EntityType.PERSON, "alice", repository_version_id=None)
    issue = node(EntityType.ISSUE, "#1 Why", repository_version_id=None)
    pull_request = node(
        EntityType.PULL_REQUEST,
        "#2 Use queues",
        details={"merged_at": "2026-08-01T00:00:00+00:00"},
        repository_version_id=None,
    )
    file = node(EntityType.FILE, "queue.py", details={"path": "src/queue.py"})
    data = HistoricalIntelligenceInput(
        nodes=(person, issue, pull_request, file),
        edges=(
            edge(person, pull_request, RelationshipType.AUTHORED),
            edge(pull_request, issue, RelationshipType.RESOLVES),
            edge(pull_request, file, RelationshipType.MODIFIES),
        ),
    )
    graph = MemoryGraphRepository()
    for item in data.nodes:
        graph.nodes[(item.repository_id, item.canonical_key)] = item
    store = MemoryIntelligenceStore()
    builder = HistoricalIntelligenceBuilder(
        graph_repository=graph,
        reader=MemoryReader(data),
        store=store,
    )

    summary = await builder.build(repository_id=REPOSITORY_ID, repository_version_id=VERSION_ID)

    assert summary == HistoricalIntelligenceSummary(
        decisions=1,
        confirmed_decisions=1,
        insufficient_evidence_decisions=0,
        decision_evidence=3,
        contributor_scores=1,
        stale_decisions=0,
    )
    decisions = [item for item in graph.nodes.values() if item.entity_type == EntityType.DECISION]
    assert len(decisions) == 1
    assert decisions[0].details["status"] == "confirmed"
    assert len(graph.evidence) == 3
    assert len(store.metrics) == 6
