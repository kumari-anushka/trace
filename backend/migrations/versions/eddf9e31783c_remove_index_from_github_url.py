"""remove index from github_url

Revision ID: eddf9e31783c
Revises: da3a55aed583
Create Date: 2026-07-18 18:32:31.316436

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "eddf9e31783c"
down_revision: str | Sequence[str] | None = "da3a55aed583"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(
        op.f("ix_repositories_github_url"),
        table_name="repositories",
    )
    op.create_unique_constraint(
        "uq_repositories_github_url",
        "repositories",
        ["github_url"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_repositories_github_url",
        "repositories",
        type_="unique",
    )
    op.create_index(
        op.f("ix_repositories_github_url"),
        "repositories",
        ["github_url"],
        unique=True,
    )
