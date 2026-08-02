"""add source file contents

Revision ID: e84ad179c230
Revises: bc782e119f04
Create Date: 2026-08-01 21:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e84ad179c230"
down_revision: str | None = "bc782e119f04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_file_contents",
        sa.Column("source_file_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("encoding", sa.String(30), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False),
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
            ["source_file_id"],
            ["source_files.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("source_file_id"),
    )
    op.create_index(
        "ix_source_file_contents_content_hash",
        "source_file_contents",
        ["content_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_source_file_contents_content_hash",
        table_name="source_file_contents",
    )
    op.drop_table("source_file_contents")
