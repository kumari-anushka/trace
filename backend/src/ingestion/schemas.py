from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.ingestion.models import IngestionJobStatus


class IngestionJobResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    repository_version_id: UUID
    status: IngestionJobStatus
    progress: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
