from pydantic import BaseModel, ConfigDict, Field


class GitHubOwner(BaseModel):
    model_config = ConfigDict(extra="ignore")

    login: str


class GitHubRepository(BaseModel):
    model_config = ConfigDict(extra="ignore")

    github_id: int = Field(alias="id")
    name: str
    full_name: str
    html_url: str
    default_branch: str
    private: bool
    archived: bool
    disabled: bool
    owner: GitHubOwner


class GitHubCommit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sha: str
