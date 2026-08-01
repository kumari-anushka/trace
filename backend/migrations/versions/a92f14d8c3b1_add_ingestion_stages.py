"""add ingestion stages

Revision ID: a92f14d8c3b1
Revises: 754cc8b68188
Create Date: 2026-08-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a92f14d8c3b1"
down_revision: str | None = "754cc8b68188"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create persistent per-job ingestion stages."""
    op.create_table(
        "ingestion_stages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_job_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "completed",
                "failed",
                "skipped",
                name="ingestion_stage_status",
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "progress",
            sa.SmallInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "position >= 0",
            name=op.f("ck_ingestion_stages_position_non_negative"),
        ),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name=op.f("ck_ingestion_stages_progress_range"),
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_job_id"],
            ["ingestion_jobs.id"],
            name=op.f("fk_ingestion_stages_ingestion_job_id_ingestion_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_stages")),
        sa.UniqueConstraint(
            "ingestion_job_id",
            "name",
            name="uq_ingestion_stages_job_name",
        ),
        sa.UniqueConstraint(
            "ingestion_job_id",
            "position",
            name="uq_ingestion_stages_job_position",
        ),
    )
    op.create_index(
        op.f("ix_ingestion_stages_ingestion_job_id"),
        "ingestion_stages",
        ["ingestion_job_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove ingestion stages."""
    op.drop_index(
        op.f("ix_ingestion_stages_ingestion_job_id"),
        table_name="ingestion_stages",
    )
    op.drop_table("ingestion_stages")

    ingestion_stage_status = sa.Enum(
        name="ingestion_stage_status",
    )
    ingestion_stage_status.drop(
        op.get_bind(),
        checkfirst=True,
    )
