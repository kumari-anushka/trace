from datetime import datetime
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from src.ingestion.schemas import IngestionJobResponse
from src.repository_versions.schemas import RepositoryVersionResponse


class RepositoryImportRequest(BaseModel):
    github_url: AnyHttpUrl


class RepositoryResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    github_id: int
    github_url: str
    owner: str
    name: str
    default_branch: str
    created_at: datetime
    updated_at: datetime


class RepositoryImportResponse(BaseModel):
    repository: RepositoryResponse
    repository_version: RepositoryVersionResponse
    ingestion_job: IngestionJobResponse


class RepositoryListResponse(BaseModel):
    repositories: list[RepositoryResponse] = Field(
        default_factory=list,
    )


class MessageResponse(BaseModel):
    message: str
