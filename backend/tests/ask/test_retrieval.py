from uuid import uuid4

from src.ask.models import QueryIntent, RetrievalMode, RetrievedEvidence
from src.ask.retrieval import AdaptiveQueryPlanner, EntityResolver, reciprocal_rank_fusion
from src.graph.models import GraphNode


def evidence(identifier: str, mode: RetrievalMode, title: str) -> RetrievedEvidence:
    return RetrievedEvidence(
        id=identifier,
        title=title,
        content="Repository evidence",
        score=0.5,
        modes=(mode,),
        source_type="source_summary",
    )


def test_planner_adapts_modes_to_decision_question() -> None:
    plan = AdaptiveQueryPlanner().plan("Why was the query architecture changed?")

    assert plan.intent is QueryIntent.DECISION
    assert plan.modes[0] is RetrievalMode.GRAPH
    assert "query" in plan.terms
    assert "why" not in plan.terms


def test_planner_prefers_contributor_signals_for_who_question() -> None:
    plan = AdaptiveQueryPlanner().plan("Who reviewed the ingestion subsystem?")

    assert plan.intent is QueryIntent.CONTRIBUTOR
    assert plan.modes == (RetrievalMode.GRAPH, RetrievalMode.METADATA)


def test_reciprocal_rank_fusion_deduplicates_and_preserves_modes() -> None:
    shared_metadata = evidence("doc:shared", RetrievalMode.METADATA, "Query service")
    shared_vector = evidence("doc:shared", RetrievalMode.VECTOR, "Query service")
    vector_only = evidence("doc:vector", RetrievalMode.VECTOR, "Other component")

    result = reciprocal_rank_fusion(
        {
            RetrievalMode.METADATA: (shared_metadata,),
            RetrievalMode.VECTOR: (vector_only, shared_vector),
        },
        terms=("query",),
        limit=10,
    )

    assert result[0].id == "doc:shared"
    assert result[0].modes == (RetrievalMode.METADATA, RetrievalMode.VECTOR)
    assert len(result) == 2


def test_entity_resolver_prefers_exact_repository_entity() -> None:
    exact = GraphNode(
        repository_id=uuid4(),
        repository_version_id=uuid4(),
        entity_type="subsystem",
        canonical_key="subsystem:query",
        name="Query",
        knowledge_kind="derived",
        confidence=0.8,
        provenance={"component": "test"},
        details={},
    )
    exact.id = uuid4()
    nearby = GraphNode(
        repository_id=exact.repository_id,
        repository_version_id=exact.repository_version_id,
        entity_type="file",
        canonical_key="file:src/query/service.py",
        name="service.py",
        knowledge_kind="deterministic",
        confidence=1.0,
        provenance={"component": "test"},
        details={},
    )
    nearby.id = uuid4()

    result = EntityResolver().resolve("Query", (nearby, exact))

    assert result[0] is exact
