from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl

from src.schemas.ingestion import IngestionJobResponse
from src.schemas.repository_snapshot import RepositorySnapshotResponse


class RepositoryCreate(BaseModel):
    github_url: HttpUrl


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner: str
    name: str
    github_url: str
    created_at: datetime


class RepositoryDetailResponse(RepositoryResponse):
    snapshots: list[RepositorySnapshotResponse]
    ingestion_jobs: list[IngestionJobResponse]


class RepositoryDeleteResponse(BaseModel):
    message: str
