from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.core.exceptions import RepositoryNotFoundError, RepositoryVersionNotFoundError
from src.graph.repository import GraphRepository, GraphSnapshot
from src.graph.service import GraphService
from src.repositories.models import Repository
from src.repositories.store import RepositoryStore
from src.repository_versions.models import RepositoryVersion
from src.repository_versions.store import RepositoryVersionStore


def make_service() -> tuple[GraphService, AsyncMock, AsyncMock, AsyncMock]:
    graph_repository = AsyncMock(spec=GraphRepository)
    repository_store = AsyncMock(spec=RepositoryStore)
    version_store = AsyncMock(spec=RepositoryVersionStore)
    return (
        GraphService(
            graph_repository=graph_repository,
            repository_store=repository_store,
            repository_version_store=version_store,
        ),
        graph_repository,
        repository_store,
        version_store,
    )


@pytest.mark.asyncio
async def test_graph_service_rejects_missing_repository() -> None:
    service, graph_repository, repository_store, version_store = make_service()
    repository_store.get_by_id.return_value = None

    with pytest.raises(RepositoryNotFoundError):
        await service.get_graph(
            repository_id=uuid4(),
            repository_version_id=uuid4(),
            limit=100,
            edge_limit=200,
            metric_limit=300,
        )

    version_store.get_by_id.assert_not_awaited()
    graph_repository.subgraph.assert_not_awaited()


@pytest.mark.asyncio
async def test_graph_service_rejects_version_from_another_repository() -> None:
    service, graph_repository, repository_store, version_store = make_service()
    repository = Repository(
        github_id=1,
        github_url="https://github.test/acme/trace",
        owner="acme",
        name="trace",
        default_branch="main",
    )
    repository.id = uuid4()
    version = RepositoryVersion(
        repository_id=uuid4(),
        commit_sha="a" * 40,
        branch="main",
    )
    version.id = uuid4()
    repository_store.get_by_id.return_value = repository
    version_store.get_by_id.return_value = version

    with pytest.raises(RepositoryVersionNotFoundError):
        await service.get_graph(
            repository_id=repository.id,
            repository_version_id=version.id,
            limit=100,
            edge_limit=200,
            metric_limit=300,
        )

    graph_repository.subgraph.assert_not_awaited()


@pytest.mark.asyncio
async def test_graph_service_forwards_valid_scoped_query() -> None:
    service, graph_repository, repository_store, version_store = make_service()
    repository = Repository(
        github_id=1,
        github_url="https://github.test/acme/trace",
        owner="acme",
        name="trace",
        default_branch="main",
    )
    repository.id = uuid4()
    version = RepositoryVersion(
        repository_id=repository.id,
        commit_sha="a" * 40,
        branch="main",
    )
    version.id = uuid4()
    snapshot = GraphSnapshot(nodes=(), edges=())
    repository_store.get_by_id.return_value = repository
    version_store.get_by_id.return_value = version
    graph_repository.subgraph.return_value = snapshot

    result = await service.get_graph(
        repository_id=repository.id,
        repository_version_id=version.id,
        limit=100,
        edge_limit=200,
        metric_limit=300,
    )

    assert result is snapshot
    graph_repository.subgraph.assert_awaited_once_with(
        repository_id=repository.id,
        repository_version_id=version.id,
        limit=100,
        edge_limit=200,
        metric_limit=300,
        entity_types=(),
        relationship_types=(),
        knowledge_kinds=(),
        metric_names=(),
        include_metrics=True,
    )


@pytest.mark.asyncio
async def test_graph_service_forwards_scoped_evidence_query() -> None:
    service, graph_repository, repository_store, version_store = make_service()
    repository = Repository(
        github_id=2,
        github_url="https://github.test/acme/evidence",
        owner="acme",
        name="evidence",
        default_branch="main",
    )
    repository.id = uuid4()
    version = RepositoryVersion(
        repository_id=repository.id,
        commit_sha="b" * 40,
        branch="main",
    )
    version.id = uuid4()
    target_edge_id = uuid4()
    repository_store.get_by_id.return_value = repository
    version_store.get_by_id.return_value = version
    graph_repository.list_evidence.return_value = ((), False)

    result = await service.get_evidence(
        repository_id=repository.id,
        repository_version_id=version.id,
        target_node_id=None,
        target_edge_id=target_edge_id,
        limit=25,
    )

    assert result == ((), False)
    graph_repository.list_evidence.assert_awaited_once_with(
        repository_id=repository.id,
        repository_version_id=version.id,
        target_node_id=None,
        target_edge_id=target_edge_id,
        limit=25,
    )
