from datetime import datetime

from pydantic import BaseModel, ConfigDict

from src.models.enums import SnapshotStatus


class RepositorySnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repository_id: int
    commit_sha: str
    default_branch: str
    status: SnapshotStatus
    created_at: datetime
