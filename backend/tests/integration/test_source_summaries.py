from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from src.db.session import async_session_factory
from src.github.models import SourceFile, SourceFileContent
from src.graph.analysis import GraphAnalysisBuilder
from src.graph.filesystem import FilesystemGraphBuilder, PostgresSourceFileReader
from src.graph.python import PostgresPythonSourceReader, PythonGraphBuilder
from src.graph.repository import PostgresGraphRepository
from src.repositories.store import RepositoryStore
from src.repository_versions.store import RepositoryVersionStore
from src.semantic.models import Document, DocumentSourceType
from src.semantic.repository import PostgresSemanticRepository
from src.semantic.source_summaries import PostgresSourceSummaryReader, SourceSummaryBuilder


@pytest.mark.integration
@pytest.mark.asyncio
async def test_source_summaries_use_graph_facts_and_persist_idempotently() -> None:
    suffix = uuid4().hex
    async with async_session_factory() as session:
        repository_store = RepositoryStore(session=session)
        repository = await repository_store.create(
            github_id=uuid4().int % (2**63 - 1),
            github_url=f"https://github.com/acme/source-summary-{suffix}",
            owner="acme",
            name=f"source-summary-{suffix}",
            default_branch="main",
        )
        version = await RepositoryVersionStore(session=session).create(
            repository_id=repository.id,
            commit_sha="7" * 40,
            branch="main",
        )
        sources = {
            "src/app/main.py": (
                "source",
                "import os\nfrom .helper import helper\n\ndef run() -> str:\n    return helper()\n",
            ),
            "src/app/helper.py": (
                "source",
                "def helper() -> str:\n    return 'ok'\n",
            ),
            "README.md": ("documentation", "# This file must not receive a source summary\n"),
        }
        files: list[tuple[SourceFile, str]] = []
        for index, (path, (file_kind, content)) in enumerate(sources.items(), start=1):
            source_file = SourceFile(
                repository_version_id=version.id,
                path=path,
                blob_sha=str(index) * 40,
                size=len(content.encode()),
                mode="100644",
                file_kind=file_kind,
                language="Markdown" if path.endswith(".md") else "Python",
            )
            session.add(source_file)
            files.append((source_file, content))
        await session.flush()
        session.add_all(
            [_source_content(source_file.id, content) for source_file, content in files]
        )
        await session.commit()

        try:
            graph_repository = PostgresGraphRepository(session=session)
            await FilesystemGraphBuilder(
                graph_repository=graph_repository,
                source_file_reader=PostgresSourceFileReader(session=session),
            ).build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            python_summary = await PythonGraphBuilder(
                graph_repository=graph_repository,
                source_reader=PostgresPythonSourceReader(session=session),
            ).build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            await GraphAnalysisBuilder(repository=graph_repository).build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            builder = SourceSummaryBuilder(
                semantic_repository=PostgresSemanticRepository(session=session),
                source_reader=PostgresSourceSummaryReader(session=session),
            )
            first = await builder.build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            await session.commit()
            second = await builder.build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            await session.commit()

            assert python_summary.parsed_files == 2
            assert python_summary.internal_imports == 1
            assert python_summary.external_imports == 1
            assert first.files == 2
            assert first.declarations == 2
            assert first.imports == 2
            assert first.missing_graph_nodes == 0
            assert second.chunks == first.chunks
            documents = (
                (
                    await session.execute(
                        select(Document)
                        .where(
                            Document.repository_id == repository.id,
                            Document.source_type == DocumentSourceType.SOURCE_SUMMARY,
                        )
                        .order_by(Document.source_key, Document.chunk_index)
                    )
                )
                .scalars()
                .all()
            )
            assert len(documents) == first.chunks
            assert {document.source_key for document in documents} == {
                "src/app/helper.py",
                "src/app/main.py",
            }
            assert all(document.source_node_id is not None for document in documents)
            main_summary = "\n".join(
                document.content
                for document in documents
                if document.source_key == "src/app/main.py"
            )
            assert "function: run" in main_summary
            assert "internal file: src/app/helper.py" in main_summary
            assert "external dependency: os" in main_summary
            assert "Degree centrality:" in main_summary
            main_document = next(
                document for document in documents if document.source_key == "src/app/main.py"
            )
            assert main_document.source_url is not None
            assert main_document.source_url.endswith(f"/blob/{version.commit_sha}/src/app/main.py")
            assert main_document.details["content_field"] == "deterministic_summary"
            assert main_document.provenance["kind"] == "deterministic_source_summary"
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
