"""add source tree SHA

Revision ID: bc782e119f04
Revises: 6f13c2b49a77
Create Date: 2026-08-01 21:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "bc782e119f04"
down_revision: str | None = "6f13c2b49a77"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "repository_versions",
        sa.Column("source_tree_sha", sa.String(40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("repository_versions", "source_tree_sha")
