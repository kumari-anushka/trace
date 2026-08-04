from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.semantic.artifacts import (
    ArtifactDocumentBuilder,
    ArtifactDocumentSource,
    ArtifactSourceReader,
)
from src.semantic.models import DocumentSourceType
from src.semantic.repository import SemanticRepository


@pytest.mark.asyncio
async def test_artifact_builder_preserves_artifact_metadata_and_prunes_each_type() -> None:
    now = datetime.now(UTC).isoformat()
    repository_id = uuid4()
    repository_version_id = uuid4()
    sources = [
        ArtifactDocumentSource(
            id=uuid4(),
            source_type=DocumentSourceType.ISSUE,
            source_key="issue:12",
            title="#12 Explain graph evidence",
            content="# Context\n\nThe graph needs citations.",
            content_field="body",
            source_url="https://github.com/acme/trace/issues/12",
            provider_table="github_issues",
            source_node_id=uuid4(),
            metadata={"number": 12, "state": "open", "updated_at": now},
        ),
        ArtifactDocumentSource(
            id=uuid4(),
            source_type=DocumentSourceType.PULL_REQUEST,
            source_key="pull_request:21",
            title="#21 Add graph evidence",
            content="Add graph evidence",
            content_field="title",
            source_url="https://github.com/acme/trace/pull/21",
            provider_table="github_pull_requests",
            source_node_id=uuid4(),
            metadata={"number": 21, "state": "merged", "updated_at": now},
        ),
        ArtifactDocumentSource(
            id=uuid4(),
            source_type=DocumentSourceType.RELEASE_NOTE,
            source_key="release:88",
            title="Trace 1.0",
            content="Architecture explorer release.",
            content_field="body",
            source_url="https://github.com/acme/trace/releases/tag/v1.0",
            provider_table="github_releases",
            source_node_id=uuid4(),
            metadata={"github_release_id": 88, "tag_name": "v1.0"},
        ),
    ]
    source_reader = AsyncMock(spec=ArtifactSourceReader)
    source_reader.list_artifact_sources.return_value = sources
    semantic_repository = AsyncMock(spec=SemanticRepository)
    semantic_repository.prune_documents.side_effect = [1, 2, 3]
    builder = ArtifactDocumentBuilder(
        semantic_repository=semantic_repository,
        source_reader=source_reader,
    )

    summary = await builder.build(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
    )

    assert summary.issues == 1
    assert summary.pull_requests == 1
    assert summary.releases == 1
    assert summary.chunks == 3
    assert summary.stale_documents == 6
    documents = [call.args[0] for call in semantic_repository.upsert_document.await_args_list]
    assert [document.source_type for document in documents] == [
        DocumentSourceType.ISSUE,
        DocumentSourceType.PULL_REQUEST,
        DocumentSourceType.RELEASE_NOTE,
    ]
    assert documents[0].metadata["content_field"] == "body"
    assert documents[0].metadata["number"] == 12
    assert documents[0].start_line == 1
    assert documents[0].source_node_id == sources[0].source_node_id
    prunes = semantic_repository.prune_documents.await_args_list
    assert [call.kwargs["source_type"] for call in prunes] == [
        DocumentSourceType.ISSUE,
        DocumentSourceType.PULL_REQUEST,
        DocumentSourceType.RELEASE_NOTE,
    ]
