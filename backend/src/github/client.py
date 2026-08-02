import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, TypeAdapter, ValidationError

from src.core.exceptions import (
    GitHubAPIError,
    GitHubRateLimitError,
    GitHubRepositoryNotFoundError,
    RetryableGitHubAPIError,
)
from src.github.schemas import (
    GitHubChangedFile,
    GitHubCommit,
    GitHubContributor,
    GitHubIssue,
    GitHubLabel,
    GitHubPullRequest,
    GitHubRelease,
    GitHubRepository,
    GitHubReview,
    GitHubTree,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)
Sleep = Callable[[float], Awaitable[None]]


class GitHubClient:
    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        api_url: str,
        token: str | None,
        max_retries: int = 3,
        max_retry_delay_seconds: float = 30.0,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self.http_client = http_client
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.max_retries = max_retries
        self.max_retry_delay_seconds = max_retry_delay_seconds
        self.sleep = sleep

    async def get_repository(self, *, owner: str, name: str) -> GitHubRepository:
        return await self._get_model(
            path=f"/repos/{owner}/{name}",
            schema=GitHubRepository,
            resource_name="repository",
            not_found_message="GitHub repository not found",
        )

    async def get_branch_head(self, *, owner: str, name: str, branch: str) -> GitHubCommit:
        return await self.get_commit(owner=owner, name=name, ref=branch)

    async def get_commit(self, *, owner: str, name: str, ref: str) -> GitHubCommit:
        return await self._get_model(
            path=f"/repos/{owner}/{name}/commits/{ref}",
            schema=GitHubCommit,
            resource_name="commit",
            not_found_message="GitHub repository branch not found",
        )

    async def get_languages(self, *, owner: str, name: str) -> dict[str, int]:
        payload, _ = await self._request_json(
            path=f"/repos/{owner}/{name}/languages",
            not_found_message="GitHub repository not found",
        )
        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, int) for key, value in payload.items()
        ):
            raise GitHubAPIError("GitHub returned an invalid language response")
        return payload

    async def get_tree(
        self,
        *,
        owner: str,
        name: str,
        tree_sha: str,
        recursive: bool = True,
    ) -> GitHubTree:
        return await self._get_model(
            path=f"/repos/{owner}/{name}/git/trees/{tree_sha}",
            params={"recursive": "1"} if recursive else None,
            schema=GitHubTree,
            resource_name="source tree",
            not_found_message="GitHub repository snapshot not found",
        )

    async def get_complete_tree(
        self,
        *,
        owner: str,
        name: str,
        tree_sha: str,
    ) -> GitHubTree:
        recursive_tree = await self.get_tree(
            owner=owner,
            name=name,
            tree_sha=tree_sha,
        )
        if not recursive_tree.truncated:
            return recursive_tree

        root = await self.get_tree(
            owner=owner,
            name=name,
            tree_sha=tree_sha,
            recursive=False,
        )
        entries = []
        pending = [("", root)]
        while pending:
            prefix, current_tree = pending.pop()
            for entry in current_tree.tree:
                path = f"{prefix}/{entry.path}" if prefix else entry.path
                normalized_entry = entry.model_copy(update={"path": path})
                entries.append(normalized_entry)
                if entry.entry_type == "tree":
                    subtree = await self.get_tree(
                        owner=owner,
                        name=name,
                        tree_sha=entry.sha,
                        recursive=False,
                    )
                    pending.append((path, subtree))

        return GitHubTree(sha=root.sha, truncated=False, tree=entries)

    async def download_snapshot_archive(
        self,
        *,
        owner: str,
        name: str,
        commit_sha: str,
        max_bytes: int,
    ) -> bytes:
        response = await self._request_response(
            path=f"/repos/{owner}/{name}/zipball/{commit_sha}",
            not_found_message="GitHub repository snapshot archive not found",
        )
        if len(response.content) > max_bytes:
            raise GitHubAPIError(
                f"GitHub repository archive exceeds the {max_bytes}-byte ingestion limit"
            )
        return response.content

    async def list_labels(self, *, owner: str, name: str, limit: int) -> list[GitHubLabel]:
        return await self._get_models(
            path=f"/repos/{owner}/{name}/labels",
            params={"sort": "created", "direction": "asc"},
            schema=GitHubLabel,
            resource_name="labels",
            limit=limit,
        )

    async def list_issues(self, *, owner: str, name: str, limit: int) -> list[GitHubIssue]:
        issues = await self._get_models(
            path=f"/repos/{owner}/{name}/issues",
            params={"state": "all", "sort": "updated", "direction": "desc"},
            schema=GitHubIssue,
            resource_name="issues",
            limit=limit,
        )
        return [issue for issue in issues if issue.pull_request is None]

    async def list_pull_requests(
        self, *, owner: str, name: str, limit: int
    ) -> list[GitHubPullRequest]:
        return await self._get_models(
            path=f"/repos/{owner}/{name}/pulls",
            params={"state": "all", "sort": "updated", "direction": "desc"},
            schema=GitHubPullRequest,
            resource_name="pull requests",
            limit=limit,
        )

    async def list_pull_request_files(
        self, *, owner: str, name: str, number: int, limit: int
    ) -> list[GitHubChangedFile]:
        return await self._get_models(
            path=f"/repos/{owner}/{name}/pulls/{number}/files",
            schema=GitHubChangedFile,
            resource_name="pull request files",
            limit=limit,
        )

    async def list_pull_request_reviews(
        self, *, owner: str, name: str, number: int, limit: int
    ) -> list[GitHubReview]:
        return await self._get_models(
            path=f"/repos/{owner}/{name}/pulls/{number}/reviews",
            schema=GitHubReview,
            resource_name="pull request reviews",
            limit=limit,
        )

    async def list_commits(
        self, *, owner: str, name: str, snapshot_sha: str, limit: int
    ) -> list[GitHubCommit]:
        return await self._get_models(
            path=f"/repos/{owner}/{name}/commits",
            params={"sha": snapshot_sha},
            schema=GitHubCommit,
            resource_name="commits",
            limit=limit,
        )

    async def list_releases(self, *, owner: str, name: str, limit: int) -> list[GitHubRelease]:
        return await self._get_models(
            path=f"/repos/{owner}/{name}/releases",
            schema=GitHubRelease,
            resource_name="releases",
            limit=limit,
        )

    async def list_contributors(
        self, *, owner: str, name: str, limit: int
    ) -> list[GitHubContributor]:
        return await self._get_models(
            path=f"/repos/{owner}/{name}/contributors",
            params={"anon": "false"},
            schema=GitHubContributor,
            resource_name="contributors",
            limit=limit,
        )

    async def _get_model(
        self,
        *,
        path: str,
        schema: type[SchemaT],
        resource_name: str,
        not_found_message: str,
        params: dict[str, str] | None = None,
    ) -> SchemaT:
        payload, _ = await self._request_json(
            path=path,
            params=params,
            not_found_message=not_found_message,
        )
        if not isinstance(payload, dict):
            raise GitHubAPIError("GitHub returned an unexpected response")
        try:
            return schema.model_validate(payload)
        except ValidationError as error:
            raise GitHubAPIError(f"GitHub returned an invalid {resource_name} response") from error

    async def _get_models(
        self,
        *,
        path: str,
        schema: type[SchemaT],
        resource_name: str,
        limit: int,
        params: dict[str, str] | None = None,
    ) -> list[SchemaT]:
        if limit <= 0:
            return []

        page_params: dict[str, str] | None = {**(params or {}), "per_page": "100"}
        next_path: str | None = path
        results: list[SchemaT] = []
        adapter = TypeAdapter(list[schema])  # type: ignore[valid-type]

        while next_path is not None and len(results) < limit:
            payload, response = await self._request_json(
                path=next_path,
                params=page_params,
                not_found_message=f"GitHub {resource_name} not found",
            )
            try:
                page = adapter.validate_python(payload)
            except ValidationError as error:
                raise GitHubAPIError(
                    f"GitHub returned an invalid {resource_name} response"
                ) from error

            results.extend(page[: limit - len(results)])
            next_link = response.links.get("next", {}).get("url")
            if next_link is not None and not next_link.startswith(self.api_url):
                raise GitHubAPIError("GitHub returned an unsafe pagination link")
            next_path = next_link
            page_params = None

        return results

    async def _request_json(
        self,
        *,
        path: str,
        not_found_message: str,
        params: dict[str, str] | None = None,
    ) -> tuple[Any, httpx.Response]:
        response = await self._request_response(
            path=path,
            params=params,
            not_found_message=not_found_message,
        )
        try:
            return response.json(), response
        except ValueError as error:
            raise GitHubAPIError("GitHub returned an invalid JSON response") from error

    async def _request_response(
        self,
        *,
        path: str,
        not_found_message: str,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        url = path if path.startswith(self.api_url) else f"{self.api_url}{path}"

        for attempt in range(self.max_retries + 1):
            try:
                response = await self.http_client.get(
                    url,
                    params=params,
                    headers=self._headers(),
                    follow_redirects=True,
                )
            except httpx.TooManyRedirects as error:
                raise GitHubAPIError(
                    "GitHub redirected this repository too many times. Use its current GitHub URL."
                ) from error
            except httpx.RequestError as error:
                if attempt < self.max_retries:
                    await self.sleep(self._retry_delay(attempt, None))
                    continue
                raise RetryableGitHubAPIError("Unable to connect to GitHub API") from error

            if response.status_code == httpx.codes.NOT_FOUND:
                raise GitHubRepositoryNotFoundError(not_found_message)

            if self._is_rate_limited(response):
                retry_after = self._rate_limit_delay(response)
                if attempt < self.max_retries and retry_after <= self.max_retry_delay_seconds:
                    await self.sleep(self._retry_delay(attempt, retry_after))
                    continue
                raise GitHubRateLimitError(retry_after_seconds=retry_after)

            if response.status_code in {408, 409, 425, 429} or response.status_code >= 500:
                if attempt < self.max_retries:
                    await self.sleep(self._retry_delay(attempt, self._retry_after(response)))
                    continue
                raise RetryableGitHubAPIError(
                    f"GitHub API request failed with status {response.status_code}"
                )

            if response.status_code == httpx.codes.FORBIDDEN:
                raise GitHubAPIError("GitHub API request was forbidden or rate limited")

            if 300 <= response.status_code < 400:
                raise GitHubAPIError(
                    "GitHub reports that this repository has moved. "
                    "Paste its current GitHub URL and try again."
                )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                raise GitHubAPIError(
                    f"GitHub API request failed with status {response.status_code}"
                ) from error

            return response

        raise AssertionError("unreachable")

    def _retry_delay(self, attempt: int, requested_delay: float | None) -> float:
        delay = requested_delay if requested_delay is not None else float(2**attempt)
        return min(delay, self.max_retry_delay_seconds)

    @staticmethod
    def _is_rate_limited(response: httpx.Response) -> bool:
        return response.status_code == 429 or (
            response.status_code == 403
            and (
                response.headers.get("x-ratelimit-remaining") == "0"
                or "retry-after" in response.headers
            )
        )

    @classmethod
    def _rate_limit_delay(cls, response: httpx.Response) -> float:
        retry_after = cls._retry_after(response)
        if retry_after is not None:
            return retry_after
        reset = response.headers.get("x-ratelimit-reset")
        if reset is None:
            return 60.0
        try:
            return max(0.0, float(reset) - datetime.now(UTC).timestamp())
        except ValueError:
            return 60.0

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        value = response.headers.get("retry-after")
        if value is None:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
            except (TypeError, ValueError):
                return None
            return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
