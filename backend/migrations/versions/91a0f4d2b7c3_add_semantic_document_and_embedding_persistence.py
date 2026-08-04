"""add semantic document and embedding persistence

Revision ID: 91a0f4d2b7c3
Revises: 3b81e2c71f4a
Create Date: 2026-08-04 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR

revision: str = "91a0f4d2b7c3"
down_revision: str | None = "3b81e2c71f4a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("repository_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_node_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_key", sa.String(2000), nullable=False),
        sa.Column("canonical_key", sa.String(2000), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.String(2000), nullable=True),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("ontology_version", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "chunk_index >= 0",
            name=op.f("ck_documents_chunk_index_non_negative"),
        ),
        sa.CheckConstraint(
            "token_count IS NULL OR token_count >= 0",
            name=op.f("ck_documents_token_count_non_negative"),
        ),
        sa.CheckConstraint(
            "start_offset IS NULL OR end_offset IS NULL OR end_offset >= start_offset",
            name=op.f("ck_documents_offset_range"),
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_version_id"],
            ["repository_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_node_id"],
            ["graph_nodes.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_version_id",
            "canonical_key",
            name="uq_documents_version_canonical_key",
        ),
    )
    op.create_index("ix_documents_repository_id", "documents", ["repository_id"])
    op.create_index(
        "ix_documents_repository_version_id",
        "documents",
        ["repository_version_id"],
    )
    op.create_index("ix_documents_source_node_id", "documents", ["source_node_id"])
    op.create_index("ix_documents_source_type", "documents", ["source_type"])

    op.create_table(
        "embedding_spaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("canonical_key", sa.String(500), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model", sa.String(500), nullable=False),
        sa.Column("model_revision", sa.String(500), nullable=True),
        sa.Column("dimensions", sa.Integer(), server_default="384", nullable=False),
        sa.Column("distance_metric", sa.String(30), server_default="cosine", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "dimensions = 384",
            name=op.f("ck_embedding_spaces_mvp_dimensions"),
        ),
        sa.CheckConstraint(
            "distance_metric = 'cosine'",
            name=op.f("ck_embedding_spaces_mvp_distance_metric"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "canonical_key",
            name="uq_embedding_spaces_canonical_key",
        ),
    )
    op.create_index(
        "uq_embedding_spaces_one_active",
        "embedding_spaces",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("repository_version_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("embedding_space_id", sa.Uuid(), nullable=False),
        sa.Column("embedding", VECTOR(384), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["repository_version_id"],
            ["repository_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["embedding_space_id"],
            ["embedding_spaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id",
            "embedding_space_id",
            name="uq_embeddings_document_space",
        ),
    )
    op.create_index("ix_embeddings_repository_id", "embeddings", ["repository_id"])
    op.create_index(
        "ix_embeddings_repository_version_id",
        "embeddings",
        ["repository_version_id"],
    )
    op.create_index("ix_embeddings_document_id", "embeddings", ["document_id"])
    op.create_index(
        "ix_embeddings_embedding_space_id",
        "embeddings",
        ["embedding_space_id"],
    )
    op.create_index(
        "ix_embeddings_embedding_hnsw_cosine",
        "embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_table("embeddings")
    op.drop_table("embedding_spaces")
    op.drop_table("documents")
