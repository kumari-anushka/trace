from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class SourceFileKind(StrEnum):
    SOURCE = "source"
    TEST = "test"
    DOCUMENTATION = "documentation"
    BINARY = "binary"
    GENERATED = "generated"
    IGNORED = "ignored"


class GitHubPerson(Base):
    """A GitHub account, deliberately separate from commit Git identities."""

    __tablename__ = "github_people"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "github_user_id",
            name="uq_github_people_repository_user",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    github_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    login: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(1000))
    html_url: Mapped[str | None] = mapped_column(String(1000))
    account_type: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SourceFile(Base):
    __tablename__ = "source_files"
    __table_args__ = (
        UniqueConstraint("repository_version_id", "path", name="uq_source_files_version_path"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repository_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path: Mapped[str] = mapped_column(String(2000), nullable=False)
    blob_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    size: Mapped[int | None] = mapped_column(BigInteger)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    file_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    language: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SourceFileContent(Base):
    __tablename__ = "source_file_contents"

    source_file_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("source_files.id", ondelete="CASCADE"),
        primary_key=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    encoding: Mapped[str] = mapped_column(String(30), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    line_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class GitHubLabel(Base):
    __tablename__ = "github_labels"
    __table_args__ = (
        UniqueConstraint("repository_id", "github_label_id", name="uq_github_labels_repository_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    github_label_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    color: Mapped[str] = mapped_column(String(6), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class GitHubIssue(Base):
    __tablename__ = "github_issues"
    __table_args__ = (
        UniqueConstraint("repository_id", "github_issue_id", name="uq_github_issues_repository_id"),
        UniqueConstraint("repository_id", "number", name="uq_github_issues_repository_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    github_issue_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    author_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("github_people.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    state_reason: Mapped[str | None] = mapped_column(String(50))
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    comments_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    html_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GitHubIssueLabel(Base):
    __tablename__ = "github_issue_labels"
    issue_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("github_issues.id", ondelete="CASCADE"), primary_key=True
    )
    label_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("github_labels.id", ondelete="CASCADE"), primary_key=True
    )


class GitHubPullRequest(Base):
    __tablename__ = "github_pull_requests"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "github_pull_request_id",
            name="uq_github_prs_repository_id",
        ),
        UniqueConstraint("repository_id", "number", name="uq_github_prs_repository_number"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    github_pull_request_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    author_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("github_people.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    html_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    head_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    base_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    merge_commit_sha: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GitHubPullRequestLabel(Base):
    __tablename__ = "github_pull_request_labels"
    pull_request_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("github_pull_requests.id", ondelete="CASCADE"),
        primary_key=True,
    )
    label_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("github_labels.id", ondelete="CASCADE"), primary_key=True
    )


class GitHubPullRequestFile(Base):
    __tablename__ = "github_pull_request_files"
    pull_request_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("github_pull_requests.id", ondelete="CASCADE"),
        primary_key=True,
    )
    filename: Mapped[str] = mapped_column(String(2000), primary_key=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    additions: Mapped[int] = mapped_column(Integer, nullable=False)
    deletions: Mapped[int] = mapped_column(Integer, nullable=False)
    changes: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_filename: Mapped[str | None] = mapped_column(String(2000))
    blob_url: Mapped[str | None] = mapped_column(String(1000))


class GitHubPullRequestReview(Base):
    __tablename__ = "github_pull_request_reviews"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "github_review_id",
            name="uq_github_reviews_repository_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    pull_request_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("github_pull_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    github_review_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    author_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("github_people.id", ondelete="SET NULL")
    )
    body: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    commit_sha: Mapped[str | None] = mapped_column(String(40))
    html_url: Mapped[str | None] = mapped_column(String(1000))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GitHubCommit(Base):
    __tablename__ = "github_commits"
    __table_args__ = (
        UniqueConstraint("repository_id", "sha", name="uq_github_commits_repository_sha"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    sha: Mapped[str] = mapped_column(String(40), nullable=False)
    author_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("github_people.id", ondelete="SET NULL")
    )
    committer_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("github_people.id", ondelete="SET NULL")
    )
    git_author_name: Mapped[str | None] = mapped_column(String(255))
    git_author_email: Mapped[str | None] = mapped_column(String(320))
    git_author_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    git_committer_name: Mapped[str | None] = mapped_column(String(255))
    git_committer_email: Mapped[str | None] = mapped_column(String(320))
    git_committer_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    html_url: Mapped[str] = mapped_column(String(1000), nullable=False)


class GitHubCommitParent(Base):
    __tablename__ = "github_commit_parents"
    commit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("github_commits.id", ondelete="CASCADE"), primary_key=True
    )
    parent_sha: Mapped[str] = mapped_column(String(40), primary_key=True)


class GitHubCommitFile(Base):
    __tablename__ = "github_commit_files"
    commit_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("github_commits.id", ondelete="CASCADE"), primary_key=True
    )
    filename: Mapped[str] = mapped_column(String(2000), primary_key=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    additions: Mapped[int] = mapped_column(Integer, nullable=False)
    deletions: Mapped[int] = mapped_column(Integer, nullable=False)
    changes: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_filename: Mapped[str | None] = mapped_column(String(2000))
    blob_url: Mapped[str | None] = mapped_column(String(1000))


class GitHubRelease(Base):
    __tablename__ = "github_releases"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "github_release_id",
            name="uq_github_releases_repository_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    github_release_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    author_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("github_people.id", ondelete="SET NULL")
    )
    tag_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_commitish: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prerelease: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    html_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GitHubContributor(Base):
    __tablename__ = "github_contributors"
    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), primary_key=True
    )
    person_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("github_people.id", ondelete="CASCADE"), primary_key=True
    )
    contributions: Mapped[int] = mapped_column(Integer, nullable=False)


class IngestionArtifactSnapshot(Base):
    """Records bounds used for a repeatable artifact ingestion run."""

    __tablename__ = "ingestion_artifact_snapshots"
    repository_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repository_versions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    bounds: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
