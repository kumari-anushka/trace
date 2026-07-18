from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl


class RepositoryCreate(BaseModel):
    github_url: HttpUrl


class RepositoryResponse(BaseModel):
    id: int
    github_url: str
    owner: str
    name: str
    default_branch: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
