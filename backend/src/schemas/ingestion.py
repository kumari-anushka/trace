from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.models.enums import IngestionJobStatus, SnapshotStatus


class IngestionCreate(BaseModel):
    commit_sha: str = Field(min_length=7, max_length=40)
    default_branch: str = Field(min_length=1, max_length=255)


class RepositorySnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repository_id: int
    commit_sha: str
    default_branch: str
    status: SnapshotStatus
    created_at: datetime


class IngestionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repository_id: int
    snapshot_id: int
    status: IngestionJobStatus
    progress: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class IngestionResponse(BaseModel):
    snapshot: RepositorySnapshotResponse
    job: IngestionJobResponse
