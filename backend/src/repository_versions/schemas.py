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
    languages: dict[str, int] | None
    source_tree_sha: str | None
    source_tree_truncated: bool | None
    created_at: datetime
