from uuid import uuid4

import pytest

from src.semantic.models import EMBEDDING_DIMENSIONS, DocumentSourceType
from src.semantic.repository import (
    DocumentInput,
    EmbeddingInput,
    PostgresSemanticRepository,
    SemanticInvariantError,
)


@pytest.mark.asyncio
async def test_rejects_invalid_document_ranges_and_embedding_vectors() -> None:
    repository = PostgresSemanticRepository(session=None)  # type: ignore[arg-type]
    with pytest.raises(SemanticInvariantError, match="end_offset"):
        await repository.upsert_document(
            DocumentInput(
                repository_id=uuid4(),
                repository_version_id=uuid4(),
                source_type=DocumentSourceType.REPOSITORY_DOCUMENTATION,
                source_key="README.md",
                canonical_key="readme:0",
                content="Trace",
                chunk_index=0,
                start_offset=10,
                end_offset=2,
                provenance={"parser": "markdown"},
            )
        )

    with pytest.raises(SemanticInvariantError, match="384 dimensions"):
        await repository.upsert_embedding(
            EmbeddingInput(
                repository_id=uuid4(),
                repository_version_id=uuid4(),
                document_id=uuid4(),
                embedding_space_id=uuid4(),
                vector=[1.0, 0.0],
                content_hash="a" * 64,
                provenance={"provider": "test"},
            )
        )

    with pytest.raises(SemanticInvariantError, match="all zero"):
        await repository.upsert_embedding(
            EmbeddingInput(
                repository_id=uuid4(),
                repository_version_id=uuid4(),
                document_id=uuid4(),
                embedding_space_id=uuid4(),
                vector=[0.0] * EMBEDDING_DIMENSIONS,
                content_hash="a" * 64,
                provenance={"provider": "test"},
            )
        )
