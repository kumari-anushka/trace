from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.semantic.documentation import (
    MAX_DOCUMENT_CHUNK_CHARS,
    DocumentationChunkBuilder,
    DocumentationSourceInput,
    DocumentationSourceReader,
    chunk_documentation,
)
from src.semantic.models import DocumentSourceType
from src.semantic.repository import SemanticRepository


def test_chunk_documentation_preserves_exact_offsets_lines_and_headings() -> None:
    content = (
        "# Trace\n\n"
        + ("architecture evidence graph " * 110)
        + "\n\n## Usage\n\n"
        + ("repository walkthrough " * 120)
        + "\n"
    )

    chunks = chunk_documentation(content)

    assert len(chunks) >= 3
    assert chunks[0].heading == "Trace"
    assert any(chunk.heading == "Usage" for chunk in chunks)
    assert all(0 < len(chunk.content) <= MAX_DOCUMENT_CHUNK_CHARS for chunk in chunks)
    assert all(chunk.content == content[chunk.start_offset : chunk.end_offset] for chunk in chunks)
    assert [chunk.start_offset for chunk in chunks] == sorted(
        chunk.start_offset for chunk in chunks
    )
    for chunk in chunks:
        assert chunk.start_line == content.count("\n", 0, chunk.start_offset) + 1
        expected_end_line = content.count("\n", 0, chunk.end_offset) + (
            0 if content[chunk.end_offset - 1] == "\n" else 1
        )
        assert chunk.end_line == expected_end_line


def test_chunk_documentation_handles_empty_and_unbroken_content() -> None:
    assert chunk_documentation(" \n\t") == ()

    chunks = chunk_documentation("x" * (MAX_DOCUMENT_CHUNK_CHARS * 2 + 17))

    assert len(chunks) == 3
    assert all(len(chunk.content) <= MAX_DOCUMENT_CHUNK_CHARS for chunk in chunks)


@pytest.mark.asyncio
async def test_builder_preserves_source_metadata_and_prunes_stale_chunks() -> None:
    repository_id = uuid4()
    repository_version_id = uuid4()
    source_node_id = uuid4()
    source = DocumentationSourceInput(
        id=uuid4(),
        path="docs/architecture.md",
        blob_sha="a" * 40,
        content="# Architecture\n\nTrace uses deterministic facts.\n",
        content_hash="b" * 64,
        source_url="https://github.com/acme/trace/blob/sha/docs/architecture.md",
        source_node_id=source_node_id,
    )
    source_reader = AsyncMock(spec=DocumentationSourceReader)
    source_reader.list_documentation_sources.return_value = [source]
    semantic_repository = AsyncMock(spec=SemanticRepository)
    semantic_repository.prune_documents.return_value = 2
    builder = DocumentationChunkBuilder(
        semantic_repository=semantic_repository,
        source_reader=source_reader,
    )

    summary = await builder.build(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
    )

    assert summary.files == 1
    assert summary.chunks == 1
    assert summary.stale_documents == 2
    document = semantic_repository.upsert_document.await_args.args[0]
    assert document.source_type is DocumentSourceType.REPOSITORY_DOCUMENTATION
    assert document.source_node_id == source_node_id
    assert document.source_key == "docs/architecture.md"
    assert document.title == "Architecture"
    assert document.start_line == 1
    assert document.end_line == 3
    assert document.source_url == source.source_url
    assert document.metadata["source_content_hash"] == source.content_hash
    retained_keys = semantic_repository.prune_documents.await_args.kwargs["retained_canonical_keys"]
    assert retained_keys == [document.canonical_key]
