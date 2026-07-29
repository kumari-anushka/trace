from typing import Any

import httpx
from pydantic import ValidationError

from src.core.exceptions import (
    GitHubAPIError,
    GitHubRepositoryNotFoundError,
)
from src.github.schemas import GitHubCommit, GitHubRepository


class GitHubClient:
    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        api_url: str,
        token: str | None,
    ) -> None:
        self.http_client = http_client
        self.api_url = api_url.rstrip("/")
        self.token = token

    async def get_repository(
        self,
        *,
        owner: str,
        name: str,
    ) -> GitHubRepository:
        payload = await self._get(
            path=f"/repos/{owner}/{name}",
            not_found_message="GitHub repository not found",
        )

        try:
            return GitHubRepository.model_validate(payload)
        except ValidationError as error:
            raise GitHubAPIError(
                "GitHub returned an invalid repository response",
            ) from error

    async def get_branch_head(
        self,
        *,
        owner: str,
        name: str,
        branch: str,
    ) -> GitHubCommit:
        payload = await self._get(
            path=f"/repos/{owner}/{name}/commits/{branch}",
            not_found_message="GitHub repository branch not found",
        )

        try:
            return GitHubCommit.model_validate(payload)
        except ValidationError as error:
            raise GitHubAPIError(
                "GitHub returned an invalid commit response",
            ) from error

    async def _get(
        self,
        *,
        path: str,
        not_found_message: str,
    ) -> dict[str, Any]:
        try:
            response = await self.http_client.get(
                f"{self.api_url}{path}",
                headers=self._headers(),
            )
        except httpx.RequestError as error:
            raise GitHubAPIError(
                "Unable to connect to GitHub API",
            ) from error

        if response.status_code == httpx.codes.NOT_FOUND:
            raise GitHubRepositoryNotFoundError(
                not_found_message,
            )

        if response.status_code == httpx.codes.FORBIDDEN:
            raise GitHubAPIError(
                "GitHub API request was forbidden or rate limited",
            )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise GitHubAPIError(
                (f"GitHub API request failed with status {response.status_code}"),
            ) from error

        try:
            payload = response.json()
        except ValueError as error:
            raise GitHubAPIError(
                "GitHub returned an invalid JSON response",
            ) from error

        if not isinstance(payload, dict):
            raise GitHubAPIError(
                "GitHub returned an unexpected response",
            )

        return payload

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        return headers
