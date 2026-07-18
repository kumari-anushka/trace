import httpx
from pydantic import SecretStr

from src.schemas.github import GitHubCommitMetadata, GitHubRepositoryMetadata


class GitHubClient:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        github_token: SecretStr | None = None,
    ) -> None:
        self.client = client
        self.github_token = github_token

    async def get_repository(
        self,
        *,
        owner: str,
        name: str,
    ) -> GitHubRepositoryMetadata:
        headers = self._build_headers()

        response = await self.client.get(
            f"/repos/{owner}/{name}",
            headers=headers,
        )
        response.raise_for_status()

        return GitHubRepositoryMetadata.model_validate(
            response.json(),
        )

    async def get_commit(
        self,
        *,
        owner: str,
        name: str,
        ref: str,
    ) -> GitHubCommitMetadata:
        response = await self.client.get(
            f"/repos/{owner}/{name}/commits/{ref}",
            headers=self._build_headers(),
        )
        response.raise_for_status()

        return GitHubCommitMetadata.model_validate(
            response.json(),
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        if self.github_token is not None:
            headers["Authorization"] = f"Bearer {self.github_token.get_secret_value()}"

        return headers
