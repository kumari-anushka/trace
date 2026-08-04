from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from src.db.session import async_session_factory
from src.github.models import SourceFile, SourceFileContent
from src.graph.filesystem import FilesystemGraphBuilder, PostgresSourceFileReader
from src.graph.javascript import JavaScriptGraphBuilder, PostgresJavaScriptSourceReader
from src.graph.models import GraphEdge, GraphEvidence, GraphNode
from src.graph.python import PostgresPythonSourceReader, PythonGraphBuilder
from src.graph.repository import PostgresGraphRepository
from src.repositories.store import RepositoryStore
from src.repository_versions.store import RepositoryVersionStore


@pytest.mark.integration
@pytest.mark.asyncio
async def test_filesystem_graph_persists_idempotently_with_evidence() -> None:
    repository_id_suffix = uuid4().hex
    async with async_session_factory() as session:
        repository_store = RepositoryStore(session=session)
        repository = await repository_store.create(
            github_id=uuid4().int % (2**63 - 1),
            github_url=f"https://github.com/acme/graph-{repository_id_suffix}",
            owner="acme",
            name=f"graph-{repository_id_suffix}",
            default_branch="main",
        )
        version = await RepositoryVersionStore(session=session).create(
            repository_id=repository.id,
            commit_sha="f" * 40,
            branch="main",
        )
        session.add_all(
            [
                SourceFile(
                    repository_version_id=version.id,
                    path="src/main.py",
                    blob_sha="a" * 40,
                    size=20,
                    mode="100644",
                    file_kind="source",
                    language="Python",
                ),
                SourceFile(
                    repository_version_id=version.id,
                    path="README.md",
                    blob_sha="b" * 40,
                    size=30,
                    mode="100644",
                    file_kind="documentation",
                    language="Markdown",
                ),
            ]
        )
        await session.commit()

        try:
            graph_repository = PostgresGraphRepository(session=session)
            builder = FilesystemGraphBuilder(
                graph_repository=graph_repository,
                source_file_reader=PostgresSourceFileReader(session=session),
            )
            for _ in range(2):
                summary = await builder.build(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                )
                await session.commit()

            assert summary.nodes == 4
            assert summary.edges == 3
            assert summary.evidence == 3
            for model, expected in (
                (GraphNode, 4),
                (GraphEdge, 3),
                (GraphEvidence, 3),
            ):
                count = (
                    await session.execute(
                        select(func.count())
                        .select_from(model)
                        .where(model.repository_id == repository.id)
                    )
                ).scalar_one()
                assert count == expected

            snapshot = await graph_repository.subgraph(
                repository_id=repository.id,
                repository_version_id=version.id,
                limit=10,
            )
            assert len(snapshot.nodes) == 4
            assert len(snapshot.edges) == 3
        finally:
            await repository_store.delete(repository)
            await session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_python_graph_persists_symbols_imports_and_source_evidence() -> None:
    repository_id_suffix = uuid4().hex
    async with async_session_factory() as session:
        repository_store = RepositoryStore(session=session)
        repository = await repository_store.create(
            github_id=uuid4().int % (2**63 - 1),
            github_url=f"https://github.com/acme/python-graph-{repository_id_suffix}",
            owner="acme",
            name=f"python-graph-{repository_id_suffix}",
            default_branch="main",
        )
        version = await RepositoryVersionStore(session=session).create(
            repository_id=repository.id,
            commit_sha="e" * 40,
            branch="main",
        )
        main_content = "import os\nfrom app.helper import help\n\ndef main():\n    return help()\n"
        helper_content = "def help():\n    return True\n"
        main_file = SourceFile(
            repository_version_id=version.id,
            path="src/app/main.py",
            blob_sha="c" * 40,
            size=len(main_content.encode()),
            mode="100644",
            file_kind="source",
            language="Python",
        )
        helper_file = SourceFile(
            repository_version_id=version.id,
            path="src/app/helper.py",
            blob_sha="d" * 40,
            size=len(helper_content.encode()),
            mode="100644",
            file_kind="source",
            language="Python",
        )
        session.add_all([main_file, helper_file])
        await session.flush()
        session.add_all(
            [
                _source_content(main_file.id, main_content),
                _source_content(helper_file.id, helper_content),
            ]
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
            for _ in range(2):
                await filesystem_builder.build(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                )
                summary = await python_builder.build(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                )
                await session.commit()

            assert summary.files == 2
            assert summary.symbols == 2
            assert summary.imports == 2
            assert summary.internal_imports == 1
            assert summary.external_imports == 1
            assert summary.failed_files == 0

            node_type_rows = await session.execute(
                select(GraphNode.entity_type, func.count())
                .where(GraphNode.repository_id == repository.id)
                .group_by(GraphNode.entity_type)
            )
            node_types: dict[str, int] = {
                entity_type: count for entity_type, count in node_type_rows.all()
            }
            assert node_types == {
                "repository_snapshot": 1,
                "directory": 2,
                "file": 2,
                "symbol": 2,
                "external_dependency": 1,
            }
            edge_type_rows = await session.execute(
                select(GraphEdge.relationship_type, func.count())
                .where(GraphEdge.repository_id == repository.id)
                .group_by(GraphEdge.relationship_type)
            )
            edge_types: dict[str, int] = {
                relationship_type: count for relationship_type, count in edge_type_rows.all()
            }
            assert edge_types == {"CONTAINS": 4, "DECLARES": 2, "IMPORTS": 2}
            evidence_count = (
                await session.execute(
                    select(func.count())
                    .select_from(GraphEvidence)
                    .where(GraphEvidence.repository_id == repository.id)
                )
            ).scalar_one()
            assert evidence_count == 8
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
        line_count=content.count("\n"),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_javascript_graph_persists_components_imports_exports_and_evidence() -> None:
    repository_id_suffix = uuid4().hex
    async with async_session_factory() as session:
        repository_store = RepositoryStore(session=session)
        repository = await repository_store.create(
            github_id=uuid4().int % (2**63 - 1),
            github_url=f"https://github.com/acme/js-graph-{repository_id_suffix}",
            owner="acme",
            name=f"js-graph-{repository_id_suffix}",
            default_branch="main",
        )
        version = await RepositoryVersionStore(session=session).create(
            repository_id=repository.id,
            commit_sha="9" * 40,
            branch="main",
        )
        app_content = (
            'import React from "react";\n'
            'import { Button } from "./Button";\n'
            "export default function App() { return <Button />; }\n"
        )
        button_content = "export const Button = () => <button />;\n"
        app_file = SourceFile(
            repository_version_id=version.id,
            path="frontend/src/App.tsx",
            blob_sha="1" * 40,
            size=len(app_content.encode()),
            mode="100644",
            file_kind="source",
            language="TypeScript",
        )
        button_file = SourceFile(
            repository_version_id=version.id,
            path="frontend/src/Button.tsx",
            blob_sha="2" * 40,
            size=len(button_content.encode()),
            mode="100644",
            file_kind="source",
            language="TypeScript",
        )
        session.add_all([app_file, button_file])
        await session.flush()
        session.add_all(
            [
                _source_content(app_file.id, app_content),
                _source_content(button_file.id, button_content),
            ]
        )
        await session.commit()

        try:
            graph_repository = PostgresGraphRepository(session=session)
            filesystem_builder = FilesystemGraphBuilder(
                graph_repository=graph_repository,
                source_file_reader=PostgresSourceFileReader(session=session),
            )
            javascript_builder = JavaScriptGraphBuilder(
                graph_repository=graph_repository,
                source_reader=PostgresJavaScriptSourceReader(session=session),
            )
            for _ in range(2):
                await filesystem_builder.build(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                )
                summary = await javascript_builder.build(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                )
                await session.commit()

            assert summary.files == 2
            assert summary.symbols == 2
            assert summary.imports == 2
            assert summary.exports == 2
            assert summary.components == 2
            assert summary.internal_imports == 1
            assert summary.external_imports == 1
            assert summary.failed_files == 0

            node_count = (
                await session.execute(
                    select(func.count())
                    .select_from(GraphNode)
                    .where(GraphNode.repository_id == repository.id)
                )
            ).scalar_one()
            edge_count = (
                await session.execute(
                    select(func.count())
                    .select_from(GraphEdge)
                    .where(GraphEdge.repository_id == repository.id)
                )
            ).scalar_one()
            evidence_count = (
                await session.execute(
                    select(func.count())
                    .select_from(GraphEvidence)
                    .where(GraphEvidence.repository_id == repository.id)
                )
            ).scalar_one()
            assert node_count == 8
            assert edge_count == 8
            assert evidence_count == 10
        finally:
            await repository_store.delete(repository)
            await session.commit()
