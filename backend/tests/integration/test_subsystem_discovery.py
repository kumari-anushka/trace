from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from src.ai.subsystems import (
    PostgresSubsystemEnrichmentReader,
    SubsystemEnrichmentBuilder,
    SubsystemEnrichmentInput,
    SubsystemEnrichmentProposal,
    SubsystemEnrichmentProviderInfo,
)
from src.db.session import async_session_factory
from src.graph.models import EntityType, GraphEdge, GraphEvidence, GraphMetric, GraphNode
from src.graph.repository import GraphMetricInput, GraphNodeInput, PostgresGraphRepository
from src.repositories.store import RepositoryStore
from src.repository_versions.store import RepositoryVersionStore
from src.semantic.subsystems import PostgresSubsystemDiscoveryStore, SubsystemDiscoveryBuilder


class IntegrationEnrichmentProvider:
    @property
    def info(self) -> SubsystemEnrichmentProviderInfo:
        return SubsystemEnrichmentProviderInfo(provider="test", model="integration-model")

    async def enrich(self, candidate: SubsystemEnrichmentInput) -> SubsystemEnrichmentProposal:
        return SubsystemEnrichmentProposal(
            name="API Layer",
            summary="Groups the repository API routes and their request and response schemas.",
            cited_evidence_ids=tuple(evidence.evidence_id for evidence in candidate.evidence),
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_subsystem_candidates_persist_idempotently_and_prune_when_signals_disagree() -> None:
    suffix = uuid4().hex
    async with async_session_factory() as session:
        repository_store = RepositoryStore(session=session)
        repository = await repository_store.create(
            github_id=uuid4().int % (2**63 - 1),
            github_url=f"https://github.com/acme/subsystems-{suffix}",
            owner="acme",
            name=f"subsystems-{suffix}",
            default_branch="main",
        )
        version = await RepositoryVersionStore(session=session).create(
            repository_id=repository.id,
            commit_sha="7" * 40,
            branch="main",
        )
        await session.commit()

        try:
            graph_repository = PostgresGraphRepository(session=session)
            file_nodes = []
            for path in ("backend/api/routes.py", "backend/api/schemas.py"):
                file_nodes.append(
                    await graph_repository.upsert_node(
                        GraphNodeInput(
                            repository_id=repository.id,
                            repository_version_id=version.id,
                            entity_type=EntityType.FILE,
                            canonical_key=f"repo:{repository.id}:snapshot:{version.id}:file:{path}",
                            name=path.rsplit("/", 1)[-1],
                            provenance={"test": True},
                            metadata={"path": path, "file_kind": "source"},
                        )
                    )
                )
            for node in file_nodes:
                await graph_repository.upsert_metric(
                    GraphMetricInput(
                        repository_id=repository.id,
                        repository_version_id=version.id,
                        node_id=node.id,
                        metric_name="community_membership",
                        scope_key=node.canonical_key,
                        value=2.0,
                        algorithm_version="test-analysis-v1",
                        metadata={"community_key": "community:api"},
                    )
                )
            await session.commit()

            store = PostgresSubsystemDiscoveryStore(session=session)
            builder = SubsystemDiscoveryBuilder(
                graph_repository=graph_repository,
                signal_reader=store,
                candidate_store=store,
            )
            for _ in range(2):
                summary = await builder.build(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                )
                await session.commit()

            assert summary.candidates == 1
            assert summary.memberships == 2
            assert await _count(session, GraphNode, repository.id, "entity_type", "subsystem") == 1
            assert (
                await _count(
                    session,
                    GraphEdge,
                    repository.id,
                    "relationship_type",
                    "PART_OF_SUBSYSTEM",
                )
                == 2
            )
            assert await _count(session, GraphEvidence, repository.id) == 2

            enrichment = await SubsystemEnrichmentBuilder(
                graph_repository=graph_repository,
                reader=PostgresSubsystemEnrichmentReader(session=session),
                provider=IntegrationEnrichmentProvider(),
            ).build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            await session.commit()

            assert enrichment.enriched == 1
            assert enrichment.confirmed == 0
            assert enrichment.retained_as_candidates == 1
            assert await _count(session, GraphEvidence, repository.id) == 3
            enriched_node = (
                await session.execute(
                    select(GraphNode).where(
                        GraphNode.repository_id == repository.id,
                        GraphNode.entity_type == "subsystem",
                    )
                )
            ).scalar_one()
            assert enriched_node.name == "API Layer"
            assert enriched_node.details["status"] == "candidate"
            assert enriched_node.confidence == pytest.approx(0.75)

            await session.execute(
                delete(GraphMetric).where(
                    GraphMetric.repository_id == repository.id,
                    GraphMetric.node_id == file_nodes[1].id,
                )
            )
            pruned = await builder.build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            await session.commit()

            assert pruned.candidates == 0
            assert pruned.stale_candidates == 1
            assert await _count(session, GraphNode, repository.id, "entity_type", "subsystem") == 0
            assert await _count(session, GraphEvidence, repository.id) == 0
        finally:
            await repository_store.delete(repository)
            await session.commit()


async def _count(
    session: object,
    model: type[GraphNode] | type[GraphEdge] | type[GraphEvidence],
    repository_id: object,
    field_name: str | None = None,
    field_value: str | None = None,
) -> int:
    statement = select(func.count()).select_from(model).where(model.repository_id == repository_id)
    if field_name is not None:
        statement = statement.where(getattr(model, field_name) == field_value)
    return int((await session.execute(statement)).scalar_one())  # type: ignore[attr-defined]
