from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base
from src.models.enums import IngestionJobStatus

if TYPE_CHECKING:
    from src.models.repository import Repository


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    __table_args__ = (
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_ingestion_jobs_progress_range",
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

    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey(
            "repository_snapshots.id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    status: Mapped[IngestionJobStatus] = mapped_column(
        Enum(
            IngestionJobStatus,
            name="ingestion_job_status",
            values_callable=lambda enum_type: [item.value for item in enum_type],
        ),
        default=IngestionJobStatus.PENDING,
        index=True,
    )

    progress: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    repository: Mapped["Repository"] = relationship(
        back_populates="ingestion_jobs",
    )
