from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class RepositoryCreate(BaseModel):
    github_url: HttpUrl
    default_branch: str = Field(min_length=1, max_length=255)


class RepositoryResponse(BaseModel):
    id: int
    github_url: str
    owner: str
    name: str
    default_branch: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
