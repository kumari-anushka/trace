from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from src.core.exceptions import InvalidGitHubRepositoryURLError


@dataclass(frozen=True, slots=True)
class GitHubRepositoryReference:
    owner: str
    name: str

    @classmethod
    def from_url(
        cls,
        github_url: str,
    ) -> GitHubRepositoryReference:
        normalized_url = github_url.strip()

        if not normalized_url:
            raise InvalidGitHubRepositoryURLError

        parsed_url = urlparse(normalized_url)

        if parsed_url.scheme != "https":
            raise InvalidGitHubRepositoryURLError

        if parsed_url.hostname not in {
            "github.com",
            "www.github.com",
        }:
            raise InvalidGitHubRepositoryURLError

        if parsed_url.port is not None:
            raise InvalidGitHubRepositoryURLError

        path_parts = [part for part in parsed_url.path.strip("/").split("/") if part]

        if len(path_parts) != 2:
            raise InvalidGitHubRepositoryURLError

        owner, name = path_parts

        if name.endswith(".git"):
            raise InvalidGitHubRepositoryURLError

        if not owner or not name:
            raise InvalidGitHubRepositoryURLError

        return cls(
            owner=owner,
            name=name,
        )

    @property
    def canonical_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.name}"
