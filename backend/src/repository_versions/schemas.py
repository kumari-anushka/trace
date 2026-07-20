from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RepositoryVersionResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    repository_id: UUID
    commit_sha: str
    branch: str
    created_at: datetime
