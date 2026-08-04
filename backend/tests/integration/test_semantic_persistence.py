from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from src.db.session import async_session_factory
from src.graph.models import GraphNode
from src.repositories.store import RepositoryStore
from src.repository_versions.store import RepositoryVersionStore
from src.semantic.models import EMBEDDING_DIMENSIONS, Document, DocumentSourceType, Embedding
from src.semantic.repository import (
    DocumentInput,
    EmbeddingInput,
    EmbeddingSpaceInput,
    PostgresSemanticRepository,
)


def _vector(first: float, second: float = 0.0) -> list[float]:
    return [first, second, *([0.0] * (EMBEDDING_DIMENSIONS - 2))]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_semantic_persistence_is_idempotent_and_filters_stale_embeddings() -> None:
    suffix = uuid4().hex
    async with async_session_factory() as session:
        repository_store = RepositoryStore(session=session)
        repository = await repository_store.create(
            github_id=uuid4().int % (2**63 - 1),
            github_url=f"https://github.com/acme/semantic-{suffix}",
            owner="acme",
            name=f"semantic-{suffix}",
            default_branch="main",
        )
        version = await RepositoryVersionStore(session=session).create(
            repository_id=repository.id,
            commit_sha="a" * 40,
            branch="main",
        )
        issue_node = GraphNode(
            repository_id=repository.id,
            repository_version_id=None,
            entity_type="issue",
            canonical_key="github:issue:42",
            name="#42 Graph explorer",
            description=None,
            knowledge_kind="deterministic",
            confidence=1.0,
            provenance={"provider": "github"},
            details={"number": 42},
        )
        session.add(issue_node)
        await session.commit()

        try:
            semantic_repository = PostgresSemanticRepository(session=session)
            first_space = await semantic_repository.upsert_embedding_space(
                EmbeddingSpaceInput(
                    canonical_key="test:first:384:cosine",
                    provider="test",
                    model="first-model",
                    provenance={"configured_by": "test"},
                    is_active=True,
                )
            )
            active_space = await semantic_repository.upsert_embedding_space(
                EmbeddingSpaceInput(
                    canonical_key="test:active:384:cosine",
                    provider="test",
                    model="active-model",
                    provenance={"configured_by": "test"},
                    is_active=True,
                )
            )
            await session.commit()
            await session.refresh(first_space)
            assert first_space.is_active is False
            assert active_space.is_active is True

            readme_input = DocumentInput(
                repository_id=repository.id,
                repository_version_id=version.id,
                source_type=DocumentSourceType.REPOSITORY_DOCUMENTATION,
                source_key="README.md",
                canonical_key="documentation:README.md:chunk:0",
                title="README",
                content="Trace maps repository structure.",
                chunk_index=0,
                token_count=5,
                start_offset=0,
                end_offset=32,
                source_url="https://github.com/acme/trace/blob/a/README.md",
                provenance={"source": "github_archive"},
                metadata={"path": "README.md"},
            )
            readme = await semantic_repository.upsert_document(readme_input)
            same_readme = await semantic_repository.upsert_document(readme_input)
            assert same_readme.id == readme.id

            pending = await semantic_repository.list_pending_documents(
                repository_id=repository.id,
                repository_version_id=version.id,
                embedding_space_id=active_space.id,
            )
            assert [document.id for document in pending] == [readme.id]

            await semantic_repository.upsert_embedding(
                EmbeddingInput(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                    document_id=readme.id,
                    embedding_space_id=active_space.id,
                    vector=_vector(1.0),
                    content_hash=readme.content_hash,
                    provenance={"provider": "test"},
                )
            )
            await session.commit()
            assert not await semantic_repository.list_pending_documents(
                repository_id=repository.id,
                repository_version_id=version.id,
                embedding_space_id=active_space.id,
            )

            changed_readme = await semantic_repository.upsert_document(
                replace(
                    readme_input,
                    content="Trace maps repository structure and history.",
                    end_offset=44,
                )
            )
            await session.commit()
            await session.refresh(changed_readme)
            pending = await semantic_repository.list_pending_documents(
                repository_id=repository.id,
                repository_version_id=version.id,
                embedding_space_id=active_space.id,
            )
            assert [document.id for document in pending] == [readme.id]
            assert not await semantic_repository.nearest_neighbors(
                repository_id=repository.id,
                repository_version_id=version.id,
                embedding_space_id=active_space.id,
                query_vector=_vector(1.0),
            )

            await semantic_repository.upsert_embedding(
                EmbeddingInput(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                    document_id=changed_readme.id,
                    embedding_space_id=active_space.id,
                    vector=_vector(1.0),
                    content_hash=changed_readme.content_hash,
                    provenance={"provider": "test"},
                )
            )
            issue = await semantic_repository.upsert_document(
                DocumentInput(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                    source_type=DocumentSourceType.ISSUE,
                    source_key="issue:42",
                    canonical_key="issue:42:chunk:0",
                    source_node_id=issue_node.id,
                    title="Graph explorer",
                    content="Add an architecture graph.",
                    chunk_index=0,
                    provenance={"source": "github_api"},
                    metadata={"number": 42},
                )
            )
            await semantic_repository.upsert_embedding(
                EmbeddingInput(
                    repository_id=repository.id,
                    repository_version_id=version.id,
                    document_id=issue.id,
                    embedding_space_id=active_space.id,
                    vector=_vector(0.0, 1.0),
                    content_hash=issue.content_hash,
                    provenance={"provider": "test"},
                )
            )
            await session.commit()

            matches = await semantic_repository.nearest_neighbors(
                repository_id=repository.id,
                repository_version_id=version.id,
                embedding_space_id=active_space.id,
                query_vector=_vector(1.0),
                limit=2,
            )
            assert [match.document.id for match in matches] == [readme.id, issue.id]
            assert matches[0].cosine_distance == pytest.approx(0.0)

            document_count = (
                await session.execute(
                    select(func.count())
                    .select_from(Document)
                    .where(Document.repository_id == repository.id)
                )
            ).scalar_one()
            embedding_count = (
                await session.execute(
                    select(func.count())
                    .select_from(Embedding)
                    .where(Embedding.repository_id == repository.id)
                )
            ).scalar_one()
            assert document_count == 2
            assert embedding_count == 2
        finally:
            await repository_store.delete(repository)
            await session.commit()
