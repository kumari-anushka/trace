from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from math import isfinite
from typing import Protocol
from uuid import UUID

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.ontology import ONTOLOGY_VERSION
from src.semantic.models import (
    EMBEDDING_DIMENSIONS,
    DistanceMetric,
    Document,
    DocumentSourceType,
    Embedding,
    EmbeddingSpace,
)

MAX_SEMANTIC_RESULTS = 100
MAX_PENDING_DOCUMENTS = 1_000


@dataclass(frozen=True, slots=True)
class DocumentInput:
    repository_id: UUID
    repository_version_id: UUID
    source_type: DocumentSourceType
    source_key: str
    canonical_key: str
    content: str
    chunk_index: int
    provenance: dict[str, object]
    source_node_id: UUID | None = None
    title: str | None = None
    token_count: int | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    start_line: int | None = None
    end_line: int | None = None
    source_url: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    ontology_version: str = ONTOLOGY_VERSION


@dataclass(frozen=True, slots=True)
class EmbeddingSpaceInput:
    canonical_key: str
    provider: str
    model: str
    provenance: dict[str, object]
    model_revision: str | None = None
    dimensions: int = EMBEDDING_DIMENSIONS
    distance_metric: DistanceMetric = DistanceMetric.COSINE
    is_active: bool = False


@dataclass(frozen=True, slots=True)
class EmbeddingInput:
    repository_id: UUID
    repository_version_id: UUID
    document_id: UUID
    embedding_space_id: UUID
    vector: Sequence[float]
    content_hash: str
    provenance: dict[str, object]
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SemanticSearchResult:
    document: Document
    cosine_distance: float


class SemanticInvariantError(ValueError):
    """Raised before invalid semantic data reaches persistence."""


class SemanticRepository(Protocol):
    async def upsert_document(self, document: DocumentInput) -> Document: ...

    async def upsert_embedding_space(self, space: EmbeddingSpaceInput) -> EmbeddingSpace: ...

    async def upsert_embedding(self, embedding: EmbeddingInput) -> Embedding: ...

    async def prune_documents(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        source_type: DocumentSourceType,
        retained_canonical_keys: Sequence[str],
    ) -> int: ...

    async def list_pending_documents(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        embedding_space_id: UUID,
        limit: int = MAX_PENDING_DOCUMENTS,
    ) -> Sequence[Document]: ...

    async def nearest_neighbors(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        embedding_space_id: UUID,
        query_vector: Sequence[float],
        limit: int = 10,
    ) -> Sequence[SemanticSearchResult]: ...


class PostgresSemanticRepository:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def upsert_document(self, document: DocumentInput) -> Document:
        _validate_required(document.source_type.value, "source_type")
        _validate_required(document.source_key, "source_key")
        _validate_required(document.canonical_key, "canonical_key")
        _validate_required(document.content, "content")
        _validate_provenance(document.provenance)
        if document.chunk_index < 0:
            raise SemanticInvariantError("chunk_index cannot be negative")
        if document.token_count is not None and document.token_count < 0:
            raise SemanticInvariantError("token_count cannot be negative")
        if (
            document.start_offset is not None
            and document.end_offset is not None
            and document.end_offset < document.start_offset
        ):
            raise SemanticInvariantError("end_offset cannot precede start_offset")
        if (
            document.start_line is not None
            and document.end_line is not None
            and document.end_line < document.start_line
        ):
            raise SemanticInvariantError("end_line cannot precede start_line")

        if document.source_node_id is not None:
            from src.graph.models import GraphNode

            source_node = await self.session.get(GraphNode, document.source_node_id)
            if (
                source_node is None
                or source_node.repository_id != document.repository_id
                or source_node.repository_version_id not in (None, document.repository_version_id)
            ):
                raise SemanticInvariantError("source_node_id is outside the document snapshot")

        content_hash = sha256(document.content.encode()).hexdigest()
        values = {
            "repository_id": document.repository_id,
            "repository_version_id": document.repository_version_id,
            "source_node_id": document.source_node_id,
            "source_type": document.source_type.value,
            "source_key": document.source_key,
            "canonical_key": document.canonical_key,
            "title": document.title,
            "content": document.content,
            "content_hash": content_hash,
            "chunk_index": document.chunk_index,
            "token_count": document.token_count,
            "start_offset": document.start_offset,
            "end_offset": document.end_offset,
            "start_line": document.start_line,
            "end_line": document.end_line,
            "source_url": document.source_url,
            "provenance": document.provenance,
            "details": document.metadata,
            "ontology_version": document.ontology_version,
        }
        insert_statement = insert(Document).values(**values)
        statement = insert_statement.on_conflict_do_update(
            constraint="uq_documents_version_canonical_key",
            set_={
                "source_node_id": insert_statement.excluded.source_node_id,
                "source_type": insert_statement.excluded.source_type,
                "source_key": insert_statement.excluded.source_key,
                "title": insert_statement.excluded.title,
                "content": insert_statement.excluded.content,
                "content_hash": insert_statement.excluded.content_hash,
                "chunk_index": insert_statement.excluded.chunk_index,
                "token_count": insert_statement.excluded.token_count,
                "start_offset": insert_statement.excluded.start_offset,
                "end_offset": insert_statement.excluded.end_offset,
                "start_line": insert_statement.excluded.start_line,
                "end_line": insert_statement.excluded.end_line,
                "source_url": insert_statement.excluded.source_url,
                "provenance": insert_statement.excluded.provenance,
                "metadata": insert_statement.excluded.metadata,
                "ontology_version": insert_statement.excluded.ontology_version,
                "updated_at": insert_statement.excluded.updated_at,
            },
        ).returning(Document)
        result = await self.session.execute(statement)
        return result.scalar_one()

    async def prune_documents(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        source_type: DocumentSourceType,
        retained_canonical_keys: Sequence[str],
    ) -> int:
        statement = delete(Document).where(
            Document.repository_id == repository_id,
            Document.repository_version_id == repository_version_id,
            Document.source_type == source_type.value,
        )
        if retained_canonical_keys:
            statement = statement.where(Document.canonical_key.not_in(retained_canonical_keys))
        result = await self.session.execute(statement)
        rowcount = getattr(result, "rowcount", 0)
        return int(rowcount or 0)

    async def upsert_embedding_space(self, space: EmbeddingSpaceInput) -> EmbeddingSpace:
        _validate_required(space.canonical_key, "canonical_key")
        _validate_required(space.provider, "provider")
        _validate_required(space.model, "model")
        _validate_provenance(space.provenance)
        if space.dimensions != EMBEDDING_DIMENSIONS:
            raise SemanticInvariantError(
                f"MVP embedding spaces must use {EMBEDDING_DIMENSIONS} dimensions"
            )
        if space.distance_metric is not DistanceMetric.COSINE:
            raise SemanticInvariantError("MVP embedding spaces must use cosine distance")
        if space.is_active:
            await self.session.execute(
                update(EmbeddingSpace)
                .where(EmbeddingSpace.is_active.is_(True))
                .values(is_active=False)
            )

        values = {
            "canonical_key": space.canonical_key,
            "provider": space.provider,
            "model": space.model,
            "model_revision": space.model_revision,
            "dimensions": space.dimensions,
            "distance_metric": space.distance_metric.value,
            "is_active": space.is_active,
            "provenance": space.provenance,
        }
        insert_statement = insert(EmbeddingSpace).values(**values)
        statement = insert_statement.on_conflict_do_update(
            constraint="uq_embedding_spaces_canonical_key",
            set_={
                "provider": insert_statement.excluded.provider,
                "model": insert_statement.excluded.model,
                "model_revision": insert_statement.excluded.model_revision,
                "dimensions": insert_statement.excluded.dimensions,
                "distance_metric": insert_statement.excluded.distance_metric,
                "is_active": insert_statement.excluded.is_active,
                "provenance": insert_statement.excluded.provenance,
                "updated_at": insert_statement.excluded.updated_at,
            },
        ).returning(EmbeddingSpace)
        result = await self.session.execute(statement)
        return result.scalar_one()

    async def upsert_embedding(self, embedding: EmbeddingInput) -> Embedding:
        vector = _validate_vector(embedding.vector)
        _validate_provenance(embedding.provenance)
        document = await self.session.get(Document, embedding.document_id)
        if (
            document is None
            or document.repository_id != embedding.repository_id
            or document.repository_version_id != embedding.repository_version_id
        ):
            raise SemanticInvariantError("document_id is outside the embedding snapshot")
        if embedding.content_hash != document.content_hash:
            raise SemanticInvariantError("embedding content_hash does not match the document")
        space = await self.session.get(EmbeddingSpace, embedding.embedding_space_id)
        if space is None:
            raise SemanticInvariantError("embedding_space_id does not exist")

        values = {
            "repository_id": embedding.repository_id,
            "repository_version_id": embedding.repository_version_id,
            "document_id": embedding.document_id,
            "embedding_space_id": embedding.embedding_space_id,
            "vector": vector,
            "content_hash": embedding.content_hash,
            "provenance": embedding.provenance,
            "details": embedding.metadata,
        }
        insert_statement = insert(Embedding).values(**values)
        statement = insert_statement.on_conflict_do_update(
            constraint="uq_embeddings_document_space",
            set_={
                "repository_id": insert_statement.excluded.repository_id,
                "repository_version_id": insert_statement.excluded.repository_version_id,
                "embedding": insert_statement.excluded.embedding,
                "content_hash": insert_statement.excluded.content_hash,
                "provenance": insert_statement.excluded.provenance,
                "metadata": insert_statement.excluded.metadata,
                "updated_at": insert_statement.excluded.updated_at,
            },
        ).returning(Embedding)
        result = await self.session.execute(statement)
        return result.scalar_one()

    async def list_pending_documents(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        embedding_space_id: UUID,
        limit: int = MAX_PENDING_DOCUMENTS,
    ) -> Sequence[Document]:
        _validate_limit(limit, maximum=MAX_PENDING_DOCUMENTS)
        statement = (
            select(Document)
            .outerjoin(
                Embedding,
                and_(
                    Embedding.document_id == Document.id,
                    Embedding.embedding_space_id == embedding_space_id,
                ),
            )
            .where(
                Document.repository_id == repository_id,
                Document.repository_version_id == repository_version_id,
                or_(Embedding.id.is_(None), Embedding.content_hash != Document.content_hash),
            )
            .order_by(Document.source_type, Document.source_key, Document.chunk_index)
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def nearest_neighbors(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
        embedding_space_id: UUID,
        query_vector: Sequence[float],
        limit: int = 10,
    ) -> Sequence[SemanticSearchResult]:
        _validate_limit(limit, maximum=MAX_SEMANTIC_RESULTS)
        vector = _validate_vector(query_vector)
        distance = Embedding.vector.cosine_distance(vector).label("cosine_distance")
        statement = (
            select(Document, distance)
            .join(Embedding, Embedding.document_id == Document.id)
            .where(
                Document.repository_id == repository_id,
                Document.repository_version_id == repository_version_id,
                Embedding.embedding_space_id == embedding_space_id,
                Embedding.content_hash == Document.content_hash,
            )
            .order_by(distance)
            .limit(limit)
        )
        rows = (await self.session.execute(statement)).all()
        return [
            SemanticSearchResult(document=document, cosine_distance=float(cosine_distance))
            for document, cosine_distance in rows
        ]


def _validate_required(value: str, field_name: str) -> None:
    if not value.strip():
        raise SemanticInvariantError(f"{field_name} cannot be empty")


def _validate_provenance(provenance: dict[str, object]) -> None:
    if not provenance:
        raise SemanticInvariantError("provenance cannot be empty")


def _validate_vector(vector: Sequence[float]) -> list[float]:
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise SemanticInvariantError(
            f"embedding vector must have {EMBEDDING_DIMENSIONS} dimensions"
        )
    normalized = [float(value) for value in vector]
    if not all(isfinite(value) for value in normalized):
        raise SemanticInvariantError("embedding vector values must be finite")
    if not any(value != 0 for value in normalized):
        raise SemanticInvariantError("cosine embedding vectors cannot be all zero")
    return normalized


def _validate_limit(limit: int, *, maximum: int) -> None:
    if limit < 1 or limit > maximum:
        raise SemanticInvariantError(f"limit must be between 1 and {maximum}")
