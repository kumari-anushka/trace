from hashlib import sha256
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from src.db.session import async_session_factory
from src.github.models import SourceFile, SourceFileContent
from src.graph.canonical import external_dependency_key, file_key, subsystem_key
from src.graph.models import (
    EntityType,
    GraphEdge,
    GraphEvidence,
    GraphNode,
    KnowledgeKind,
    RelationshipType,
)
from src.graph.repository import GraphEdgeInput, GraphNodeInput, PostgresGraphRepository
from src.repositories.store import RepositoryStore
from src.repository_versions.store import RepositoryVersionStore
from src.semantic.architecture import ArchitectureBuilder, PostgresArchitectureStore
from src.semantic.subsystem_graph import PostgresSubsystemGraphStore, SubsystemGraphBuilder


@pytest.mark.integration
@pytest.mark.asyncio
async def test_architecture_summary_is_idempotent_and_prunes_stale_fact_edges() -> None:
    suffix = uuid4().hex
    async with async_session_factory() as session:
        repository_store = RepositoryStore(session=session)
        repository = await repository_store.create(
            github_id=uuid4().int % (2**63 - 1),
            github_url=f"https://github.com/acme/architecture-{suffix}",
            owner="acme",
            name=f"architecture-{suffix}",
            default_branch="main",
        )
        version = await RepositoryVersionStore(session=session).create(
            repository_id=repository.id,
            commit_sha="8" * 40,
            branch="main",
        )
        manifest_content = '{"bin": {"trace": "src/command.ts"}}'
        source_inputs = [
            _source(version.id, "package.json", "JSON", manifest_content),
            _source(version.id, "src/command.ts", "TypeScript", "export function run() {}"),
            _source(version.id, "src/app.py", "Python", "import fastapi\n"),
        ]
        sources = [source for source, _ in source_inputs]
        session.add_all(sources)
        await session.flush()
        contents = [
            _content(source.id, content)
            for source, (_, content) in zip(sources, source_inputs, strict=True)
        ]
        session.add_all(contents)
        await session.commit()

        try:
            graph_repository = PostgresGraphRepository(session=session)
            file_nodes = {}
            for source in sources:
                file_nodes[source.path] = await graph_repository.upsert_node(
                    GraphNodeInput(
                        repository_id=repository.id,
                        repository_version_id=version.id,
                        entity_type=EntityType.FILE,
                        canonical_key=file_key(repository.id, version.id, source.path),
                        name=source.path.rsplit("/", 1)[-1],
                        provenance={"test": True},
                        metadata={
                            "path": source.path,
                            "file_kind": "source",
                            "language": source.language,
                        },
                    )
                )
            dependency = await graph_repository.upsert_node(
                GraphNodeInput(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                    entity_type=EntityType.EXTERNAL_DEPENDENCY,
                    canonical_key=external_dependency_key(
                        repository.id, version.id, "python", "fastapi"
                    ),
                    name="fastapi",
                    provenance={"test": True},
                    metadata={"ecosystem": "python", "dependency_kind": "package"},
                )
            )
            await graph_repository.upsert_edge(
                GraphEdgeInput(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                    source_node_id=file_nodes["src/app.py"].id,
                    target_node_id=dependency.id,
                    relationship_type=RelationshipType.IMPORTS,
                    provenance={"test": True},
                )
            )
            api_subsystem = await graph_repository.upsert_node(
                GraphNodeInput(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                    entity_type=EntityType.SUBSYSTEM,
                    canonical_key=subsystem_key(
                        repository.id,
                        version.id,
                        (file_nodes["src/app.py"].canonical_key,),
                    ),
                    name="API",
                    description="Confirmed API subsystem.",
                    knowledge_kind=KnowledgeKind.INFERRED,
                    confidence=0.9,
                    provenance={"test": True},
                    metadata={"status": "confirmed", "member_count": 1},
                )
            )
            cli_subsystem = await graph_repository.upsert_node(
                GraphNodeInput(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                    entity_type=EntityType.SUBSYSTEM,
                    canonical_key=subsystem_key(
                        repository.id,
                        version.id,
                        (file_nodes["src/command.ts"].canonical_key,),
                    ),
                    name="CLI",
                    description="Confirmed CLI subsystem.",
                    knowledge_kind=KnowledgeKind.INFERRED,
                    confidence=0.85,
                    provenance={"test": True},
                    metadata={"status": "confirmed", "member_count": 1},
                )
            )
            for file_node, subsystem_node in (
                (file_nodes["src/app.py"], api_subsystem),
                (file_nodes["src/command.ts"], cli_subsystem),
            ):
                await graph_repository.upsert_edge(
                    GraphEdgeInput(
                        repository_id=repository.id,
                        repository_version_id=version.id,
                        source_node_id=file_node.id,
                        target_node_id=subsystem_node.id,
                        relationship_type=RelationshipType.PART_OF_SUBSYSTEM,
                        knowledge_kind=KnowledgeKind.INFERRED,
                        confidence=subsystem_node.confidence,
                        provenance={"test": True},
                    )
                )
            await graph_repository.upsert_edge(
                GraphEdgeInput(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                    source_node_id=file_nodes["src/command.ts"].id,
                    target_node_id=file_nodes["src/app.py"].id,
                    relationship_type=RelationshipType.IMPORTS,
                    provenance={"test": True},
                )
            )
            await session.commit()

            subsystem_graph_store = PostgresSubsystemGraphStore(session=session)
            subsystem_graph = await SubsystemGraphBuilder(
                graph_repository=graph_repository,
                reader=subsystem_graph_store,
                store=subsystem_graph_store,
            ).build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            await session.commit()

            assert subsystem_graph.dependencies == 1
            assert subsystem_graph.evidence == 1

            store = PostgresArchitectureStore(session=session)
            builder = ArchitectureBuilder(
                graph_repository=graph_repository,
                reader=store,
                store=store,
            )
            for _ in range(2):
                summary = await builder.build(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                )
                await session.commit()

            assert summary.entry_points == 1
            assert summary.major_external_dependencies == 1
            assert summary.confirmed_subsystems == 2
            assert await _count(session, GraphNode, repository.id, "architecture_summary") == 1
            assert await _count(session, GraphEdge, repository.id) == 9
            assert await _count(session, GraphEvidence, repository.id) == 5

            manifest_source = sources[0]
            manifest_row = contents[0]
            manifest_row.content = "{}"
            manifest_row.content_hash = sha256(b"{}").hexdigest()
            await session.flush()
            rebuilt = await builder.build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            await session.commit()

            assert manifest_source.path == "package.json"
            assert rebuilt.entry_points == 0
            assert rebuilt.stale_edges == 1
            assert await _count(session, GraphEdge, repository.id) == 8
            assert await _count(session, GraphEvidence, repository.id) == 4
            architecture_node = (
                await session.execute(
                    select(GraphNode).where(
                        GraphNode.repository_id == repository.id,
                        GraphNode.entity_type == EntityType.ARCHITECTURE_SUMMARY,
                    )
                )
            ).scalar_one()
            assert architecture_node.details["entry_points"] == []
            confirmed_subsystems = cast(
                list[dict[str, object]],
                architecture_node.details["confirmed_subsystems"],
            )
            confirmed_ids = {item["node_id"] for item in confirmed_subsystems}
            assert confirmed_ids == {str(api_subsystem.id), str(cli_subsystem.id)}
        finally:
            await repository_store.delete(repository)
            await session.commit()


def _source(
    repository_version_id: UUID,
    path: str,
    language: str,
    content: str,
) -> tuple[SourceFile, str]:
    source = SourceFile(
        repository_version_id=repository_version_id,
        path=path,
        blob_sha=sha256(path.encode()).hexdigest()[:40],
        size=len(content.encode()),
        mode="100644",
        file_kind="source",
        language=language,
    )
    return source, content


def _content(source_file_id: UUID, content: str) -> SourceFileContent:
    return SourceFileContent(
        source_file_id=source_file_id,
        content=content,
        content_hash=sha256(content.encode()).hexdigest(),
        encoding="utf-8",
        byte_size=len(content.encode()),
        line_count=max(1, len(content.splitlines())),
    )


async def _count(
    session: object,
    model: type[GraphNode] | type[GraphEdge] | type[GraphEvidence],
    repository_id: object,
    entity_type: str | None = None,
) -> int:
    statement = select(func.count()).select_from(model).where(model.repository_id == repository_id)
    if entity_type is not None:
        statement = statement.where(GraphNode.entity_type == entity_type)
    return int((await session.execute(statement)).scalar_one())  # type: ignore[attr-defined]
