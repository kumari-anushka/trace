"""add repository graph persistence

Revision ID: 3b81e2c71f4a
Revises: e84ad179c230
Create Date: 2026-08-02 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3b81e2c71f4a"
down_revision: str | None = "e84ad179c230"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "repository_versions",
        sa.Column(
            "ontology_version",
            sa.String(20),
            server_default="1.0.0",
            nullable=False,
        ),
    )

    op.create_table(
        "graph_nodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("repository_version_id", sa.Uuid(), nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("canonical_key", sa.String(2000), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("knowledge_kind", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("ontology_version", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_graph_nodes_confidence_range"),
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["repository_version_id"], ["repository_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id",
            "canonical_key",
            name="uq_graph_nodes_repository_canonical_key",
        ),
    )
    op.create_index("ix_graph_nodes_repository_id", "graph_nodes", ["repository_id"])
    op.create_index(
        "ix_graph_nodes_repository_version_id", "graph_nodes", ["repository_version_id"]
    )
    op.create_index("ix_graph_nodes_entity_type", "graph_nodes", ["entity_type"])

    op.create_table(
        "graph_edges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("repository_version_id", sa.Uuid(), nullable=True),
        sa.Column("source_node_id", sa.Uuid(), nullable=False),
        sa.Column("target_node_id", sa.Uuid(), nullable=False),
        sa.Column("relationship_type", sa.String(50), nullable=False),
        sa.Column("knowledge_kind", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("ontology_version", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "source_node_id <> target_node_id",
            name=op.f("ck_graph_edges_no_self_loop"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_graph_edges_confidence_range"),
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["repository_version_id"], ["repository_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["source_node_id"], ["graph_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["graph_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id",
            "source_node_id",
            "target_node_id",
            "relationship_type",
            name="uq_graph_edges_relation_identity",
        ),
    )
    op.create_index("ix_graph_edges_repository_id", "graph_edges", ["repository_id"])
    op.create_index(
        "ix_graph_edges_repository_version_id", "graph_edges", ["repository_version_id"]
    )
    op.create_index("ix_graph_edges_relationship_type", "graph_edges", ["relationship_type"])
    op.create_index("ix_graph_edges_source_node_id", "graph_edges", ["source_node_id"])
    op.create_index("ix_graph_edges_target_node_id", "graph_edges", ["target_node_id"])

    op.create_table(
        "evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("repository_version_id", sa.Uuid(), nullable=True),
        sa.Column("canonical_key", sa.String(2000), nullable=False),
        sa.Column("source_node_id", sa.Uuid(), nullable=False),
        sa.Column("target_node_id", sa.Uuid(), nullable=True),
        sa.Column("target_edge_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_type", sa.String(50), nullable=False),
        sa.Column("relationship", sa.String(50), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("source_url", sa.String(2000), nullable=True),
        sa.Column("start_line", sa.Integer(), nullable=True),
        sa.Column("end_line", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(target_node_id IS NOT NULL) <> (target_edge_id IS NOT NULL)",
            name=op.f("ck_evidence_exactly_one_target"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_evidence_confidence_range"),
        ),
        sa.CheckConstraint(
            "start_line IS NULL OR end_line IS NULL OR end_line >= start_line",
            name=op.f("ck_evidence_line_range"),
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["repository_version_id"], ["repository_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["source_node_id"], ["graph_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_node_id"], ["graph_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_edge_id"], ["graph_edges.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id",
            "canonical_key",
            name="uq_evidence_repository_canonical_key",
        ),
    )
    op.create_index("ix_evidence_repository_id", "evidence", ["repository_id"])
    op.create_index(
        "ix_evidence_repository_version_id",
        "evidence",
        ["repository_version_id"],
    )
    op.create_index("ix_evidence_source_node_id", "evidence", ["source_node_id"])
    op.create_index("ix_evidence_target_node_id", "evidence", ["target_node_id"])
    op.create_index("ix_evidence_target_edge_id", "evidence", ["target_edge_id"])

    op.create_table(
        "graph_metrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("repository_version_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=True),
        sa.Column("metric_name", sa.String(100), nullable=False),
        sa.Column("scope_key", sa.String(2000), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("algorithm_version", sa.String(50), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["repository_version_id"], ["repository_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["node_id"], ["graph_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_version_id",
            "metric_name",
            "scope_key",
            "algorithm_version",
            name="uq_graph_metrics_version_metric_scope_algorithm",
        ),
    )
    op.create_index("ix_graph_metrics_repository_id", "graph_metrics", ["repository_id"])
    op.create_index(
        "ix_graph_metrics_repository_version_id", "graph_metrics", ["repository_version_id"]
    )
    op.create_index("ix_graph_metrics_node_id", "graph_metrics", ["node_id"])


def downgrade() -> None:
    op.drop_table("graph_metrics")
    op.drop_table("evidence")
    op.drop_table("graph_edges")
    op.drop_table("graph_nodes")
    op.drop_column("repository_versions", "ontology_version")
