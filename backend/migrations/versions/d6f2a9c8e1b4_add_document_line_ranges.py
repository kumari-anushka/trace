"""add document line ranges

Revision ID: d6f2a9c8e1b4
Revises: 91a0f4d2b7c3
Create Date: 2026-08-04 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6f2a9c8e1b4"
down_revision: str | None = "91a0f4d2b7c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("start_line", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("end_line", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f("ck_documents_line_range"),
        "documents",
        "start_line IS NULL OR end_line IS NULL OR end_line >= start_line",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_documents_line_range"), "documents", type_="check")
    op.drop_column("documents", "end_line")
    op.drop_column("documents", "start_line")
