from __future__ import annotations

from collections.abc import Sequence
from math import sqrt
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.semantic.embeddings import (
    EmbeddingBuilder,
    EmbeddingProviderInfo,
    LocalHashingEmbeddingProvider,
)
from src.semantic.models import EMBEDDING_DIMENSIONS, Document, EmbeddingSpace
from src.semantic.repository import SemanticRepository


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_magnitude = sqrt(sum(value * value for value in left))
    right_magnitude = sqrt(sum(value * value for value in right))
    return numerator / (left_magnitude * right_magnitude)


@pytest.mark.asyncio
async def test_local_hashing_embeddings_are_deterministic_and_lexically_useful() -> None:
    provider = LocalHashingEmbeddingProvider()
    texts = [
        "repository graph architecture dependencies",
        "repository graph architecture modules",
        "calendar meeting availability reminder",
    ]

    first = await provider.embed(texts)
    second = await provider.embed(texts)

    assert first == second
    assert all(len(vector) == EMBEDDING_DIMENSIONS for vector in first)
    assert all(sum(value * value for value in vector) == pytest.approx(1.0) for vector in first)
    assert _cosine(first[0], first[1]) > _cosine(first[0], first[2])


@pytest.mark.asyncio
async def test_embedding_builder_consumes_pending_documents_in_batches() -> None:
    repository_id = uuid4()
    repository_version_id = uuid4()
    space = EmbeddingSpace(
        canonical_key="local:test:v1:384:cosine",
        provider="local",
        model="test",
        dimensions=EMBEDDING_DIMENSIONS,
        distance_metric="cosine",
        is_active=True,
        provenance={"test": True},
    )
    space.id = uuid4()
    documents = [
        Document(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            source_type="source_summary",
            source_key=f"src/file_{index}.py",
            canonical_key=f"source:{index}",
            content=f"module {index} repository graph",
            content_hash=str(index) * 64,
            chunk_index=0,
            provenance={"test": True},
            details={},
        )
        for index in range(2)
    ]
    for document in documents:
        document.id = uuid4()

    semantic_repository = AsyncMock(spec=SemanticRepository)
    semantic_repository.upsert_embedding_space.return_value = space
    semantic_repository.list_pending_documents.side_effect = [documents, []]
    builder = EmbeddingBuilder(
        semantic_repository=semantic_repository,
        provider=LocalHashingEmbeddingProvider(),
        batch_size=2,
    )

    summary = await builder.build(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
    )

    assert summary.documents == 2
    assert summary.batches == 1
    assert summary.dimensions == EMBEDDING_DIMENSIONS
    assert semantic_repository.upsert_embedding.await_count == 2
    inputs = [call.args[0] for call in semantic_repository.upsert_embedding.await_args_list]
    assert [embedding.document_id for embedding in inputs] == [
        document.id for document in documents
    ]
    assert all(embedding.embedding_space_id == space.id for embedding in inputs)
    assert all(len(embedding.vector) == EMBEDDING_DIMENSIONS for embedding in inputs)


class WrongCardinalityProvider:
    @property
    def info(self) -> EmbeddingProviderInfo:
        return EmbeddingProviderInfo(
            provider="test",
            model="wrong-cardinality",
            model_revision="v1",
            dimensions=EMBEDDING_DIMENSIONS,
        )

    async def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return []


@pytest.mark.asyncio
async def test_embedding_builder_rejects_provider_cardinality_mismatches() -> None:
    repository_id = uuid4()
    repository_version_id = uuid4()
    document = Document(
        repository_id=repository_id,
        repository_version_id=repository_version_id,
        source_type="issue",
        source_key="issue:1",
        canonical_key="issue:1:0",
        content="graph issue",
        content_hash="a" * 64,
        chunk_index=0,
        provenance={"test": True},
        details={},
    )
    document.id = uuid4()
    space = EmbeddingSpace(
        canonical_key="test:wrong-cardinality:v1:384:cosine",
        provider="test",
        model="wrong-cardinality",
        dimensions=EMBEDDING_DIMENSIONS,
        distance_metric="cosine",
        is_active=True,
        provenance={"test": True},
    )
    space.id = uuid4()
    semantic_repository = AsyncMock(spec=SemanticRepository)
    semantic_repository.upsert_embedding_space.return_value = space
    semantic_repository.list_pending_documents.return_value = [document]

    with pytest.raises(RuntimeError, match="different number of vectors"):
        await EmbeddingBuilder(
            semantic_repository=semantic_repository,
            provider=WrongCardinalityProvider(),
        ).build(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
        )
