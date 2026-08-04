from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from src.db.session import async_session_factory
from src.github.models import SourceFile, SourceFileContent
from src.graph.filesystem import FilesystemGraphBuilder, PostgresSourceFileReader
from src.graph.repository import PostgresGraphRepository
from src.repositories.store import RepositoryStore
from src.repository_versions.store import RepositoryVersionStore
from src.semantic.documentation import (
    DocumentationChunkBuilder,
    PostgresDocumentationSourceReader,
)
from src.semantic.models import Document
from src.semantic.repository import PostgresSemanticRepository


def _source_content(source_file_id: UUID, content: str) -> SourceFileContent:
    encoded = content.encode()
    return SourceFileContent(
        source_file_id=source_file_id,
        content=content,
        content_hash=sha256(encoded).hexdigest(),
        encoding="utf-8",
        byte_size=len(encoded),
        line_count=content.count("\n") + (not content.endswith("\n")),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_documentation_chunks_persist_idempotently_and_prune_stale_rows() -> None:
    suffix = uuid4().hex
    async with async_session_factory() as session:
        repository_store = RepositoryStore(session=session)
        repository = await repository_store.create(
            github_id=uuid4().int % (2**63 - 1),
            github_url=f"https://github.com/acme/docs-{suffix}",
            owner="acme",
            name=f"docs-{suffix}",
            default_branch="main",
        )
        version = await RepositoryVersionStore(session=session).create(
            repository_id=repository.id,
            commit_sha="d" * 40,
            branch="main",
        )
        documentation = (
            "# Trace\n\n"
            + ("architecture evidence graph " * 120)
            + "\n\n## Usage\n\n"
            + ("repository walkthrough " * 140)
            + "\n"
        )
        readme = SourceFile(
            repository_version_id=version.id,
            path="README.md",
            blob_sha="a" * 40,
            size=len(documentation.encode()),
            mode="100644",
            file_kind="documentation",
            language="Markdown",
        )
        source = SourceFile(
            repository_version_id=version.id,
            path="src/main.py",
            blob_sha="b" * 40,
            size=12,
            mode="100644",
            file_kind="source",
            language="Python",
        )
        session.add_all([readme, source])
        await session.flush()
        readme_content = _source_content(readme.id, documentation)
        session.add_all([readme_content, _source_content(source.id, "print('ok')\n")])
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
            builder = DocumentationChunkBuilder(
                semantic_repository=PostgresSemanticRepository(session=session),
                source_reader=PostgresDocumentationSourceReader(session=session),
            )
            first_summary = await builder.build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            await session.commit()
            second_summary = await builder.build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            await session.commit()

            assert first_summary.files == 1
            assert first_summary.chunks >= 3
            assert second_summary.chunks == first_summary.chunks
            documents = (
                (
                    await session.execute(
                        select(Document)
                        .where(Document.repository_id == repository.id)
                        .order_by(Document.chunk_index)
                    )
                )
                .scalars()
                .all()
            )
            assert len(documents) == first_summary.chunks
            assert all(document.source_node_id is not None for document in documents)
            assert all(document.source_key == "README.md" for document in documents)
            for document in documents:
                assert document.start_offset is not None
                assert document.end_offset is not None
                assert (
                    document.content == documentation[document.start_offset : document.end_offset]
                )
            assert documents[0].source_url is not None
            assert documents[0].source_url.endswith(f"/blob/{version.commit_sha}/README.md")

            shortened = "# Trace\n\nA concise repository atlas.\n"
            shortened_bytes = shortened.encode()
            readme_content.content = shortened
            readme_content.content_hash = sha256(shortened_bytes).hexdigest()
            readme_content.byte_size = len(shortened_bytes)
            readme_content.line_count = 3
            await session.commit()
            summary = await builder.build(
                repository_id=repository.id,
                repository_version_id=version.id,
            )
            await session.commit()

            document_count = (
                await session.execute(
                    select(func.count())
                    .select_from(Document)
                    .where(Document.repository_id == repository.id)
                )
            ).scalar_one()
            assert summary.chunks == 1
            assert summary.stale_documents == first_summary.chunks - 1
            assert document_count == 1
        finally:
            await repository_store.delete(repository)
            await session.commit()
