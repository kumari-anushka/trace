import httpx
from pydantic import SecretStr


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
    ) -> dict[str, object]:
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        if self.github_token is not None:
            headers["Authorization"] = f"Bearer {self.github_token.get_secret_value()}"

        response = await self.client.get(
            f"/repos/{owner}/{name}",
            headers=headers,
        )
        response.raise_for_status()

        data: dict[str, object] = response.json()
        return data
