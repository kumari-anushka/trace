from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base
from src.models.enums import SnapshotStatus

if TYPE_CHECKING:
    from src.models.repository import Repository


class RepositorySnapshot(Base):
    __tablename__ = "repository_snapshots"

    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "commit_sha",
            name="uq_repository_snapshots_repository_commit",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    repository_id: Mapped[int] = mapped_column(
        ForeignKey(
            "repositories.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    commit_sha: Mapped[str] = mapped_column(String(40))

    default_branch: Mapped[str] = mapped_column(String(255))

    status: Mapped[SnapshotStatus] = mapped_column(
        Enum(
            SnapshotStatus,
            name="snapshot_status",
            values_callable=lambda enum_type: [item.value for item in enum_type],
        ),
        default=SnapshotStatus.PENDING,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    repository: Mapped["Repository"] = relationship(
        back_populates="snapshots",
    )
