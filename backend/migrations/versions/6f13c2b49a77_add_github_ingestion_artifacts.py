"""add GitHub ingestion artifacts

Revision ID: 6f13c2b49a77
Revises: d41b8e7c2a90
Create Date: 2026-08-01 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6f13c2b49a77"
down_revision: str | None = "d41b8e7c2a90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("repositories", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("repositories", sa.Column("homepage", sa.String(1000), nullable=True))
    op.add_column("repositories", sa.Column("primary_language", sa.String(100), nullable=True))
    for column_name in (
        "stars_count",
        "forks_count",
        "watchers_count",
        "open_issues_count",
    ):
        op.add_column(
            "repositories",
            sa.Column(column_name, sa.Integer(), server_default="0", nullable=False),
        )
    op.add_column(
        "repositories",
        sa.Column("archived", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "repositories",
        sa.Column("disabled", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    for column_name in (
        "provider_created_at",
        "provider_updated_at",
        "provider_pushed_at",
    ):
        op.add_column(
            "repositories",
            sa.Column(column_name, sa.DateTime(timezone=True), nullable=True),
        )

    op.add_column("repository_versions", sa.Column("languages", sa.JSON(), nullable=True))
    op.add_column(
        "repository_versions",
        sa.Column("source_tree_truncated", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("ingestion_jobs", sa.Column("output_summary", sa.JSON(), nullable=True))
    op.add_column("ingestion_stages", sa.Column("output_summary", sa.JSON(), nullable=True))

    op.create_table(
        "github_people",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("github_user_id", sa.BigInteger(), nullable=False),
        sa.Column("login", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.String(1000), nullable=True),
        sa.Column("html_url", sa.String(1000), nullable=True),
        sa.Column("account_type", sa.String(50), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id", "github_user_id", name="uq_github_people_repository_user"
        ),
    )
    op.create_index("ix_github_people_repository_id", "github_people", ["repository_id"])

    op.create_table(
        "source_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_version_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(2000), nullable=False),
        sa.Column("blob_sha", sa.String(40), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=True),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("file_kind", sa.String(30), nullable=False),
        sa.Column("language", sa.String(100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["repository_version_id"], ["repository_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_version_id", "path", name="uq_source_files_version_path"),
    )
    op.create_index(
        "ix_source_files_repository_version_id", "source_files", ["repository_version_id"]
    )

    op.create_table(
        "github_labels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("github_label_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("color", sa.String(6), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id", "github_label_id", name="uq_github_labels_repository_id"
        ),
    )

    op.create_table(
        "github_issues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("github_issue_id", sa.BigInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("state_reason", sa.String(50), nullable=True),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("comments_count", sa.Integer(), nullable=False),
        sa.Column("html_url", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["author_id"], ["github_people.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id", "github_issue_id", name="uq_github_issues_repository_id"
        ),
        sa.UniqueConstraint("repository_id", "number", name="uq_github_issues_repository_number"),
    )

    op.create_table(
        "github_pull_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("github_pull_request_id", sa.BigInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("draft", sa.Boolean(), nullable=False),
        sa.Column("locked", sa.Boolean(), nullable=False),
        sa.Column("html_url", sa.String(1000), nullable=False),
        sa.Column("head_sha", sa.String(40), nullable=False),
        sa.Column("base_sha", sa.String(40), nullable=False),
        sa.Column("merge_commit_sha", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["author_id"], ["github_people.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id", "github_pull_request_id", name="uq_github_prs_repository_id"
        ),
        sa.UniqueConstraint("repository_id", "number", name="uq_github_prs_repository_number"),
    )

    op.create_table(
        "github_commits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("sha", sa.String(40), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("committer_id", sa.Uuid(), nullable=True),
        sa.Column("git_author_name", sa.String(255), nullable=True),
        sa.Column("git_author_email", sa.String(320), nullable=True),
        sa.Column("git_author_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("git_committer_name", sa.String(255), nullable=True),
        sa.Column("git_committer_email", sa.String(320), nullable=True),
        sa.Column("git_committer_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("html_url", sa.String(1000), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["github_people.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["committer_id"], ["github_people.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "sha", name="uq_github_commits_repository_sha"),
    )

    op.create_table(
        "github_releases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("github_release_id", sa.BigInteger(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("tag_name", sa.String(255), nullable=False),
        sa.Column("target_commitish", sa.String(255), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("draft", sa.Boolean(), nullable=False),
        sa.Column("prerelease", sa.Boolean(), nullable=False),
        sa.Column("html_url", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["author_id"], ["github_people.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id", "github_release_id", name="uq_github_releases_repository_id"
        ),
    )

    op.create_table(
        "github_issue_labels",
        sa.Column("issue_id", sa.Uuid(), nullable=False),
        sa.Column("label_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["github_issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["label_id"], ["github_labels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("issue_id", "label_id"),
    )
    op.create_table(
        "github_pull_request_labels",
        sa.Column("pull_request_id", sa.Uuid(), nullable=False),
        sa.Column("label_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["pull_request_id"], ["github_pull_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["label_id"], ["github_labels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pull_request_id", "label_id"),
    )
    op.create_table(
        "github_pull_request_files",
        sa.Column("pull_request_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(2000), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("additions", sa.Integer(), nullable=False),
        sa.Column("deletions", sa.Integer(), nullable=False),
        sa.Column("changes", sa.Integer(), nullable=False),
        sa.Column("previous_filename", sa.String(2000), nullable=True),
        sa.Column("blob_url", sa.String(1000), nullable=True),
        sa.ForeignKeyConstraint(
            ["pull_request_id"], ["github_pull_requests.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("pull_request_id", "filename"),
    )
    op.create_table(
        "github_pull_request_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("pull_request_id", sa.Uuid(), nullable=False),
        sa.Column("github_review_id", sa.BigInteger(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=True),
        sa.Column("html_url", sa.String(1000), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["author_id"], ["github_people.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["pull_request_id"], ["github_pull_requests.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "repository_id", "github_review_id", name="uq_github_reviews_repository_id"
        ),
    )
    op.create_table(
        "github_commit_parents",
        sa.Column("commit_id", sa.Uuid(), nullable=False),
        sa.Column("parent_sha", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["commit_id"], ["github_commits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("commit_id", "parent_sha"),
    )
    op.create_table(
        "github_commit_files",
        sa.Column("commit_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(2000), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("additions", sa.Integer(), nullable=False),
        sa.Column("deletions", sa.Integer(), nullable=False),
        sa.Column("changes", sa.Integer(), nullable=False),
        sa.Column("previous_filename", sa.String(2000), nullable=True),
        sa.Column("blob_url", sa.String(1000), nullable=True),
        sa.ForeignKeyConstraint(["commit_id"], ["github_commits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("commit_id", "filename"),
    )
    op.create_table(
        "github_contributors",
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("contributions", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["github_people.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("repository_id", "person_id"),
    )
    op.create_table(
        "ingestion_artifact_snapshots",
        sa.Column("repository_version_id", sa.Uuid(), nullable=False),
        sa.Column("bounds", sa.JSON(), nullable=False),
        sa.Column(
            "ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["repository_version_id"], ["repository_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("repository_version_id"),
    )


def downgrade() -> None:
    for table_name in (
        "ingestion_artifact_snapshots",
        "github_contributors",
        "github_commit_files",
        "github_commit_parents",
        "github_pull_request_reviews",
        "github_pull_request_files",
        "github_pull_request_labels",
        "github_issue_labels",
        "github_releases",
        "github_commits",
        "github_pull_requests",
        "github_issues",
        "github_labels",
        "source_files",
        "github_people",
    ):
        op.drop_table(table_name)

    op.drop_column("ingestion_stages", "output_summary")
    op.drop_column("ingestion_jobs", "output_summary")
    op.drop_column("repository_versions", "source_tree_truncated")
    op.drop_column("repository_versions", "languages")
    for column_name in (
        "provider_pushed_at",
        "provider_updated_at",
        "provider_created_at",
        "disabled",
        "archived",
        "open_issues_count",
        "watchers_count",
        "forks_count",
        "stars_count",
        "primary_language",
        "homepage",
        "description",
    ):
        op.drop_column("repositories", column_name)
