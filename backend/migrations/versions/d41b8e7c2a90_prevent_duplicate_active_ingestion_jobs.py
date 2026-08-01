"""prevent duplicate active ingestion jobs

Revision ID: d41b8e7c2a90
Revises: a92f14d8c3b1
Create Date: 2026-08-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d41b8e7c2a90"
down_revision: str | None = "a92f14d8c3b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "uq_ingestion_jobs_active_repository_version"


def upgrade() -> None:
    """Allow at most one active job for each immutable snapshot."""
    op.create_index(
        INDEX_NAME,
        "ingestion_jobs",
        ["repository_version_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('pending', 'queued', 'running')",
        ),
    )


def downgrade() -> None:
    """Remove active-job uniqueness enforcement."""
    op.drop_index(
        INDEX_NAME,
        table_name="ingestion_jobs",
    )
