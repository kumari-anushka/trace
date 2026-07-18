from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.models.ingestion_job import IngestionJob
    from src.models.repository_snapshot import RepositorySnapshot


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True)
    github_url: Mapped[str] = mapped_column(
        String(500),
        unique=True,
    )
    owner: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    snapshots: Mapped[list["RepositorySnapshot"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )

    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
    )
