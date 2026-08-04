from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.graph.models import EntityType, EvidenceType, RelationshipType
from src.graph.repository import (
    GraphEdgeInput,
    GraphEvidenceInput,
    GraphInvariantError,
    GraphMetricInput,
    GraphNodeInput,
    PostgresGraphRepository,
)


def make_repository() -> tuple[PostgresGraphRepository, AsyncMock]:
    session = AsyncMock(spec=AsyncSession)
    return PostgresGraphRepository(session=session), session


@pytest.mark.asyncio
async def test_node_requires_bounded_confidence_and_provenance() -> None:
    repository, session = make_repository()
    invalid = GraphNodeInput(
        repository_id=uuid4(),
        repository_version_id=uuid4(),
        entity_type=EntityType.FILE,
        canonical_key="file:src/main.py",
        name="main.py",
        confidence=1.1,
        provenance={"parser": "python_ast"},
    )

    with pytest.raises(GraphInvariantError, match="confidence"):
        await repository.upsert_node(invalid)

    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_edge_rejects_self_loop_before_querying_database() -> None:
    repository, session = make_repository()
    node_id = uuid4()
    invalid = GraphEdgeInput(
        repository_id=uuid4(),
        repository_version_id=uuid4(),
        source_node_id=node_id,
        target_node_id=node_id,
        relationship_type=RelationshipType.CONTAINS,
        provenance={"provider": "github"},
    )

    with pytest.raises(GraphInvariantError, match="self-loops"):
        await repository.upsert_edge(invalid)

    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_evidence_requires_exactly_one_target() -> None:
    repository, session = make_repository()
    invalid = GraphEvidenceInput(
        repository_id=uuid4(),
        repository_version_id=uuid4(),
        canonical_key="evidence:one",
        source_node_id=uuid4(),
        evidence_type=EvidenceType.PROVIDER_RELATION,
        provenance={"provider": "github"},
    )

    with pytest.raises(GraphInvariantError, match="exactly one"):
        await repository.upsert_evidence(invalid)

    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_metric_rejects_non_finite_values() -> None:
    repository, session = make_repository()
    invalid = GraphMetricInput(
        repository_id=uuid4(),
        repository_version_id=uuid4(),
        metric_name="degree_centrality",
        scope_key="node:one",
        value=float("nan"),
        algorithm_version="networkx-test",
    )

    with pytest.raises(GraphInvariantError, match="finite"):
        await repository.upsert_metric(invalid)

    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_graph_queries_reject_limits_before_querying_database() -> None:
    repository, session = make_repository()

    with pytest.raises(GraphInvariantError, match="edge limit"):
        await repository.subgraph(
            repository_id=uuid4(),
            repository_version_id=uuid4(),
            edge_limit=2_001,
        )

    with pytest.raises(GraphInvariantError, match="depth"):
        await repository.neighbors(
            repository_id=uuid4(),
            repository_version_id=uuid4(),
            node_id=uuid4(),
            depth=4,
        )

    session.execute.assert_not_awaited()
