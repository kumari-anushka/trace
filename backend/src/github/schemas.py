from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GitHubModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class GitHubOwner(GitHubModel):
    github_id: int = Field(alias="id", default=0)
    login: str
    avatar_url: str | None = None
    html_url: str | None = None
    account_type: str | None = Field(alias="type", default=None)


class GitHubRepository(GitHubModel):
    github_id: int = Field(alias="id")
    name: str
    full_name: str
    html_url: str
    default_branch: str
    private: bool
    archived: bool
    disabled: bool
    owner: GitHubOwner
    description: str | None = None
    homepage: str | None = None
    language: str | None = None
    stargazers_count: int = 0
    forks_count: int = 0
    watchers_count: int = 0
    open_issues_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    pushed_at: datetime | None = None


class GitHubGitIdentity(GitHubModel):
    name: str | None = None
    email: str | None = None
    date: datetime | None = None


class GitHubCommitParent(GitHubModel):
    sha: str


class GitHubCommitDetails(GitHubModel):
    author: GitHubGitIdentity | None = None
    committer: GitHubGitIdentity | None = None
    message: str = ""
    tree: GitHubCommitParent | None = None


class GitHubChangedFile(GitHubModel):
    filename: str
    status: str
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    previous_filename: str | None = None
    blob_url: str | None = None


class GitHubCommit(GitHubModel):
    sha: str
    html_url: str = ""
    author: GitHubOwner | None = None
    committer: GitHubOwner | None = None
    commit: GitHubCommitDetails = Field(default_factory=GitHubCommitDetails)
    parents: list[GitHubCommitParent] = Field(default_factory=list)
    files: list[GitHubChangedFile] = Field(default_factory=list)


class GitHubTreeEntry(GitHubModel):
    path: str
    mode: str
    entry_type: str = Field(alias="type")
    sha: str
    size: int | None = None


class GitHubTree(GitHubModel):
    sha: str
    truncated: bool = False
    tree: list[GitHubTreeEntry]


class GitHubLabel(GitHubModel):
    github_id: int = Field(alias="id")
    name: str
    color: str
    description: str | None = None


class GitHubIssue(GitHubModel):
    github_id: int = Field(alias="id")
    number: int
    user: GitHubOwner | None = None
    title: str
    body: str | None = None
    state: str
    state_reason: str | None = None
    locked: bool = False
    comments: int = 0
    html_url: str
    labels: list[GitHubLabel] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    pull_request: dict[str, object] | None = None


class GitHubPullRequestRef(GitHubModel):
    sha: str


class GitHubPullRequest(GitHubModel):
    github_id: int = Field(alias="id")
    number: int
    user: GitHubOwner | None = None
    title: str
    body: str | None = None
    state: str
    draft: bool = False
    locked: bool = False
    html_url: str
    head: GitHubPullRequestRef
    base: GitHubPullRequestRef
    merge_commit_sha: str | None = None
    labels: list[GitHubLabel] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    merged_at: datetime | None = None


class GitHubReview(GitHubModel):
    github_id: int = Field(alias="id")
    user: GitHubOwner | None = None
    body: str | None = None
    state: str
    commit_id: str | None = None
    html_url: str | None = None
    submitted_at: datetime | None = None


class GitHubRelease(GitHubModel):
    github_id: int = Field(alias="id")
    author: GitHubOwner | None = None
    tag_name: str
    target_commitish: str
    name: str | None = None
    body: str | None = None
    draft: bool = False
    prerelease: bool = False
    html_url: str
    created_at: datetime
    published_at: datetime | None = None


class GitHubContributor(GitHubOwner):
    contributions: int = 0
