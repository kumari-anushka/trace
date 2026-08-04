from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from src.core.exceptions import GraphNodeNotFoundError
from src.db.session import async_session_factory
from src.github.models import SourceFile, SourceFileContent
from src.graph.analysis import GraphAnalysisBuilder
from src.graph.filesystem import FilesystemGraphBuilder, PostgresSourceFileReader
from src.graph.models import EntityType, GraphMetric, GraphNode, RelationshipType
from src.graph.python import PostgresPythonSourceReader, PythonGraphBuilder
from src.graph.repository import GraphAnalysisLimitError, PostgresGraphRepository
from src.repositories.store import RepositoryStore
from src.repository_versions.store import RepositoryVersionStore


@pytest.mark.integration
@pytest.mark.asyncio
async def test_graph_analysis_replaces_idempotent_metrics_for_a_snapshot() -> None:
    suffix = uuid4().hex
    async with async_session_factory() as session:
        repository_store = RepositoryStore(session=session)
        repository = await repository_store.create(
            github_id=uuid4().int % (2**63 - 1),
            github_url=f"https://github.com/acme/analysis-{suffix}",
            owner="acme",
            name=f"analysis-{suffix}",
            default_branch="main",
        )
        version = await RepositoryVersionStore(session=session).create(
            repository_id=repository.id,
            commit_sha="3" * 40,
            branch="main",
        )
        sources = {
            "src/a.py": "import b\n",
            "src/b.py": "import c\n",
            "src/c.py": "import a\n",
        }
        files = []
        for index, (path, content) in enumerate(sources.items(), start=1):
            source_file = SourceFile(
                repository_version_id=version.id,
                path=path,
                blob_sha=str(index) * 40,
                size=len(content.encode()),
                mode="100644",
                file_kind="source",
                language="Python",
            )
            files.append((source_file, content))
            session.add(source_file)
        await session.flush()
        session.add_all(
            [_source_content(source_file.id, content) for source_file, content in files]
        )
        await session.commit()

        try:
            graph_repository = PostgresGraphRepository(session=session)
            filesystem_builder = FilesystemGraphBuilder(
                graph_repository=graph_repository,
                source_file_reader=PostgresSourceFileReader(session=session),
            )
            python_builder = PythonGraphBuilder(
                graph_repository=graph_repository,
                source_reader=PostgresPythonSourceReader(session=session),
            )
            analysis_builder = GraphAnalysisBuilder(repository=graph_repository)

            await filesystem_builder.build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            python_summary = await python_builder.build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            for _ in range(2):
                summary = await analysis_builder.build(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                )
                await session.commit()

            assert python_summary.internal_imports == 3
            assert summary.nodes == 5
            assert summary.edges == 7
            assert summary.connected_components == 1
            assert summary.communities == 1
            assert summary.bridges == 1
            assert summary.dependency_cycles == 1
            assert summary.metrics == 21

            with pytest.raises(GraphAnalysisLimitError, match="node safety limit"):
                await graph_repository.load_for_analysis(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                    max_nodes=4,
                )

            metric_count = (
                await session.execute(
                    select(func.count())
                    .select_from(GraphMetric)
                    .where(
                        GraphMetric.repository_id == repository.id,
                        GraphMetric.repository_version_id == version.id,
                    )
                )
            ).scalar_one()
            assert metric_count == summary.metrics

            metric_names = set(
                (
                    await session.execute(
                        select(GraphMetric.metric_name).where(
                            GraphMetric.repository_version_id == version.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert {"degree_centrality", "bridge", "dependency_cycle"} <= metric_names

            filtered = await graph_repository.subgraph(
                repository_id=repository.id,
                repository_version_id=version.id,
                limit=2,
                edge_limit=10,
                metric_limit=10,
                entity_types=(EntityType.FILE,),
                relationship_types=(RelationshipType.IMPORTS,),
                metric_names=("degree_centrality",),
            )
            assert len(filtered.nodes) == 2
            assert len(filtered.edges) == 1
            assert len(filtered.metrics) == 2
            assert filtered.nodes_truncated is True
            assert filtered.edges_truncated is False
            assert filtered.metrics_truncated is False

            root = (
                await session.execute(
                    select(GraphNode).where(
                        GraphNode.repository_id == repository.id,
                        GraphNode.entity_type == EntityType.FILE,
                        GraphNode.name == "a.py",
                    )
                )
            ).scalar_one()
            neighborhood = await graph_repository.neighbors(
                repository_id=repository.id,
                repository_version_id=version.id,
                node_id=root.id,
                depth=1,
                limit=10,
                edge_limit=10,
                metric_limit=10,
                entity_types=(EntityType.FILE,),
                relationship_types=(RelationshipType.IMPORTS,),
                include_metrics=False,
            )
            assert len(neighborhood.nodes) == 3
            assert len(neighborhood.edges) == 3
            assert neighborhood.metrics == ()

            with pytest.raises(GraphNodeNotFoundError):
                await graph_repository.neighbors(
                    repository_id=repository.id,
                    repository_version_id=uuid4(),
                    node_id=root.id,
                )
        finally:
            await repository_store.delete(repository)
            await session.commit()


def _source_content(source_file_id: UUID, content: str) -> SourceFileContent:
    encoded = content.encode()
    return SourceFileContent(
        source_file_id=source_file_id,
        content=content,
        content_hash=sha256(encoded).hexdigest(),
        encoding="utf-8",
        byte_size=len(encoded),
        line_count=len(content.splitlines()),
    )
