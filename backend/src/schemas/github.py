from pydantic import BaseModel


class GitHubRepositoryMetadata(BaseModel):
    id: int
    name: str
    full_name: str
    default_branch: str
    private: bool


class GitHubCommitMetadata(BaseModel):
    sha: str
