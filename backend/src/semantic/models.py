from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pgvector.sqlalchemy import VECTOR
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.core.ontology import ONTOLOGY_VERSION
from src.db.base import Base

EMBEDDING_DIMENSIONS = 384


class DocumentSourceType(StrEnum):
    REPOSITORY_DOCUMENTATION = "repository_documentation"
    SOURCE_SUMMARY = "source_summary"
    ISSUE = "issue"
    PULL_REQUEST = "pull_request"
    RELEASE_NOTE = "release_note"


class DistanceMetric(StrEnum):
    COSINE = "cosine"


class Document(Base):
    """One evidence-preserving, retrievable source chunk."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "repository_version_id",
            "canonical_key",
            name="uq_documents_version_canonical_key",
        ),
        CheckConstraint("chunk_index >= 0", name="chunk_index_non_negative"),
        CheckConstraint(
            "token_count IS NULL OR token_count >= 0",
            name="token_count_non_negative",
        ),
        CheckConstraint(
            "start_offset IS NULL OR end_offset IS NULL OR end_offset >= start_offset",
            name="offset_range",
        ),
        CheckConstraint(
            "start_line IS NULL OR end_line IS NULL OR end_line >= start_line",
            name="line_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repository_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_node_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("graph_nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(2000), nullable=False)
    canonical_key: Mapped[str] = mapped_column(String(2000), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    provenance: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    details: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    ontology_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ONTOLOGY_VERSION
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class EmbeddingSpace(Base):
    __tablename__ = "embedding_spaces"
    __table_args__ = (
        UniqueConstraint("canonical_key", name="uq_embedding_spaces_canonical_key"),
        CheckConstraint(
            f"dimensions = {EMBEDDING_DIMENSIONS}",
            name="mvp_dimensions",
        ),
        CheckConstraint("distance_metric = 'cosine'", name="mvp_distance_metric"),
        Index(
            "uq_embedding_spaces_one_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    canonical_key: Mapped[str] = mapped_column(String(500), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(500), nullable=False)
    model_revision: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dimensions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=EMBEDDING_DIMENSIONS,
        server_default=str(EMBEDDING_DIMENSIONS),
    )
    distance_metric: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=DistanceMetric.COSINE.value,
        server_default=DistanceMetric.COSINE.value,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    provenance: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Embedding(Base):
    __tablename__ = "embeddings"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "embedding_space_id",
            name="uq_embeddings_document_space",
        ),
        Index(
            "ix_embeddings_embedding_hnsw_cosine",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repository_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repository_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    embedding_space_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("embedding_spaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vector: Mapped[list[float]] = mapped_column(
        "embedding",
        VECTOR(EMBEDDING_DIMENSIONS),
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provenance: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    details: Mapped[dict[str, object]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
