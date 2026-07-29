from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.ingestion.models import IngestionJob
    from src.repositories.models import Repository


class RepositoryVersion(Base):
    __tablename__ = "repository_versions"

    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "commit_sha",
            name="uq_repository_versions_repository_commit",
        ),
        CheckConstraint(
            "char_length(commit_sha) = 40",
            name="commit_sha_length",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    repository_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "repositories.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    commit_sha: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    branch: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    repository: Mapped[Repository] = relationship(
        back_populates="versions",
    )

    ingestion_jobs: Mapped[list[IngestionJob]] = relationship(
        back_populates="repository_version",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
