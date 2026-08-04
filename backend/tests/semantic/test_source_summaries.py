from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.graph.models import EntityType
from src.semantic.models import DocumentSourceType
from src.semantic.repository import SemanticRepository
from src.semantic.source_summaries import (
    MAX_SUMMARY_RELATIONS,
    SOURCE_SUMMARY_VERSION,
    SourceSummaryBuilder,
    SourceSummaryInput,
    SourceSummaryReader,
    SourceSummaryRelation,
)


@pytest.mark.asyncio
async def test_source_summary_builder_preserves_graph_facts_and_bounds_relations() -> None:
    repository_id = uuid4()
    repository_version_id = uuid4()
    source_node_id = uuid4()
    declarations = tuple(
        SourceSummaryRelation(
            edge_id=uuid4(),
            entity_type=EntityType.SYMBOL,
            name=f"function_{index}",
            symbol_kind="function",
            qualified_name=f"module.function_{index}",
        )
        for index in range(MAX_SUMMARY_RELATIONS + 2)
    )
    imports = (
        SourceSummaryRelation(
            edge_id=uuid4(),
            entity_type=EntityType.FILE,
            name="helpers.py",
            path="src/helpers.py",
        ),
        SourceSummaryRelation(
            edge_id=uuid4(),
            entity_type=EntityType.EXTERNAL_DEPENDENCY,
            name="fastapi",
        ),
    )
    source = SourceSummaryInput(
        id=uuid4(),
        path="src/main.py",
        blob_sha="a" * 40,
        file_kind="source",
        language="Python",
        size=512,
        content_hash="b" * 64,
        source_url="https://github.com/acme/trace/blob/cccc/src/main.py",
        source_node_id=source_node_id,
        declarations=declarations,
        imports=imports,
        degree_centrality=0.25,
        community_index=3,
    )
    source_reader = AsyncMock(spec=SourceSummaryReader)
    source_reader.list_source_summary_inputs.return_value = [source]
    semantic_repository = AsyncMock(spec=SemanticRepository)
    semantic_repository.prune_documents.return_value = 4
    builder = SourceSummaryBuilder(
        semantic_repository=semantic_repository,
        source_reader=source_reader,
    )

    summary = await builder.build(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
    )

    assert summary.files == 1
    assert summary.declarations == MAX_SUMMARY_RELATIONS + 2
    assert summary.imports == 2
    assert summary.truncated_declarations == 2
    assert summary.truncated_imports == 0
    assert summary.missing_graph_nodes == 0
    assert summary.stale_documents == 4
    documents = [call.args[0] for call in semantic_repository.upsert_document.await_args_list]
    assert len(documents) == summary.chunks
    assert all(document.source_type is DocumentSourceType.SOURCE_SUMMARY for document in documents)
    assert all(document.source_node_id == source_node_id for document in documents)
    combined_content = "\n".join(document.content for document in documents)
    assert "function: module.function_0" in combined_content
    assert "internal file: src/helpers.py" in combined_content
    assert "external dependency: fastapi" in combined_content
    assert "2 additional declarations omitted" in combined_content
    assert "Degree centrality: 0.250000" in combined_content
    first = documents[0]
    assert first.metadata["content_field"] == "deterministic_summary"
    assert first.metadata["algorithm_version"] == SOURCE_SUMMARY_VERSION
    assert first.metadata["blob_sha"] == "a" * 40
    assert first.provenance["source_content_hash"] == "b" * 64
    assert len(first.provenance["relation_edge_ids"]) == MAX_SUMMARY_RELATIONS + 2
    semantic_repository.prune_documents.assert_awaited_once_with(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        source_type=DocumentSourceType.SOURCE_SUMMARY,
        retained_canonical_keys=[document.canonical_key for document in documents],
    )


@pytest.mark.asyncio
async def test_source_summary_builder_records_missing_graph_nodes() -> None:
    source = SourceSummaryInput(
        id=uuid4(),
        path="tests/test_main.py",
        blob_sha="d" * 40,
        file_kind="test",
        language="Python",
        size=None,
        content_hash=None,
        source_url="https://github.com/acme/trace/blob/eeee/tests/test_main.py",
        source_node_id=None,
        declarations=(),
        imports=(),
    )
    source_reader = AsyncMock(spec=SourceSummaryReader)
    source_reader.list_source_summary_inputs.return_value = [source]
    semantic_repository = AsyncMock(spec=SemanticRepository)
    semantic_repository.prune_documents.return_value = 0

    summary = await SourceSummaryBuilder(
        semantic_repository=semantic_repository,
        source_reader=source_reader,
    ).build(repository_id=uuid4(), repository_version_id=uuid4())

    assert summary.missing_graph_nodes == 1
    document = semantic_repository.upsert_document.await_args.args[0]
    assert document.source_node_id is None
    assert "None detected" in document.content
