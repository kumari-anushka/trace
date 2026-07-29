from collections.abc import Callable
from typing import Any

import httpx
import pytest

from src.core.exceptions import (
    GitHubAPIError,
    GitHubRepositoryNotFoundError,
)
from src.github.client import GitHubClient

RequestHandler = Callable[
    [httpx.Request],
    httpx.Response,
]


def create_github_client(
    handler: RequestHandler,
    *,
    token: str | None = "test-token",
) -> tuple[GitHubClient, httpx.AsyncClient]:
    transport = httpx.MockTransport(handler)

    http_client = httpx.AsyncClient(
        transport=transport,
    )

    github_client = GitHubClient(
        http_client=http_client,
        api_url="https://api.github.com",
        token=token,
    )

    return github_client, http_client


def repository_payload() -> dict[str, Any]:
    return {
        "id": 123456789,
        "name": "trace",
        "full_name": "kumari-anushka/trace",
        "html_url": "https://github.com/kumari-anushka/trace",
        "default_branch": "main",
        "private": False,
        "archived": False,
        "disabled": False,
        "owner": {
            "login": "kumari-anushka",
        },
    }


@pytest.mark.asyncio
async def test_get_repository_returns_repository() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "GET"
        assert request.url == ("https://api.github.com/repos/kumari-anushka/trace")
        assert request.headers["Authorization"] == ("Bearer test-token")
        assert request.headers["Accept"] == ("application/vnd.github+json")
        assert request.headers["X-GitHub-Api-Version"] == ("2022-11-28")

        return httpx.Response(
            status_code=200,
            json=repository_payload(),
        )

    github_client, http_client = create_github_client(handler)

    try:
        repository = await github_client.get_repository(
            owner="kumari-anushka",
            name="trace",
        )
    finally:
        await http_client.aclose()

    assert repository.github_id == 123456789
    assert repository.name == "trace"
    assert repository.full_name == "kumari-anushka/trace"
    assert repository.html_url == ("https://github.com/kumari-anushka/trace")
    assert repository.default_branch == "main"
    assert repository.private is False
    assert repository.archived is False
    assert repository.disabled is False
    assert repository.owner.login == "kumari-anushka"


@pytest.mark.asyncio
async def test_get_repository_omits_authorization_without_token() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert "Authorization" not in request.headers

        return httpx.Response(
            status_code=200,
            json=repository_payload(),
        )

    github_client, http_client = create_github_client(
        handler,
        token=None,
    )

    try:
        await github_client.get_repository(
            owner="kumari-anushka",
            name="trace",
        )
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_get_branch_head_returns_commit() -> None:
    commit_sha = "a" * 40

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "GET"
        assert request.url == ("https://api.github.com/repos/kumari-anushka/trace/commits/main")

        return httpx.Response(
            status_code=200,
            json={
                "sha": commit_sha,
            },
        )

    github_client, http_client = create_github_client(handler)

    try:
        commit = await github_client.get_branch_head(
            owner="kumari-anushka",
            name="trace",
            branch="main",
        )
    finally:
        await http_client.aclose()

    assert commit.sha == commit_sha


@pytest.mark.asyncio
async def test_get_repository_raises_when_not_found() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=404,
            request=request,
        )

    github_client, http_client = create_github_client(handler)

    try:
        with pytest.raises(
            GitHubRepositoryNotFoundError,
            match="GitHub repository not found",
        ):
            await github_client.get_repository(
                owner="missing",
                name="repository",
            )
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_get_branch_head_raises_when_branch_not_found() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=404,
            request=request,
        )

    github_client, http_client = create_github_client(handler)

    try:
        with pytest.raises(
            GitHubRepositoryNotFoundError,
            match="GitHub repository branch not found",
        ):
            await github_client.get_branch_head(
                owner="kumari-anushka",
                name="trace",
                branch="missing",
            )
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_get_repository_raises_for_forbidden_response() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=403,
            request=request,
        )

    github_client, http_client = create_github_client(handler)

    try:
        with pytest.raises(
            GitHubAPIError,
            match="GitHub API request was forbidden or rate limited",
        ):
            await github_client.get_repository(
                owner="kumari-anushka",
                name="trace",
            )
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_get_repository_raises_for_http_error() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=500,
            request=request,
        )

    github_client, http_client = create_github_client(handler)

    try:
        with pytest.raises(
            GitHubAPIError,
            match="GitHub API request failed with status 500",
        ):
            await github_client.get_repository(
                owner="kumari-anushka",
                name="trace",
            )
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_get_repository_raises_for_network_error() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ConnectError(
            "Connection failed",
            request=request,
        )

    github_client, http_client = create_github_client(handler)

    try:
        with pytest.raises(
            GitHubAPIError,
            match="Unable to connect to GitHub API",
        ):
            await github_client.get_repository(
                owner="kumari-anushka",
                name="trace",
            )
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_get_repository_raises_for_invalid_json() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            content=b"invalid-json",
            request=request,
        )

    github_client, http_client = create_github_client(handler)

    try:
        with pytest.raises(
            GitHubAPIError,
            match="GitHub returned an invalid JSON response",
        ):
            await github_client.get_repository(
                owner="kumari-anushka",
                name="trace",
            )
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_get_repository_raises_for_non_object_response() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json=[],
            request=request,
        )

    github_client, http_client = create_github_client(handler)

    try:
        with pytest.raises(
            GitHubAPIError,
            match="GitHub returned an unexpected response",
        ):
            await github_client.get_repository(
                owner="kumari-anushka",
                name="trace",
            )
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_get_repository_raises_for_invalid_schema() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "id": 123456789,
            },
            request=request,
        )

    github_client, http_client = create_github_client(handler)

    try:
        with pytest.raises(
            GitHubAPIError,
            match="GitHub returned an invalid repository response",
        ):
            await github_client.get_repository(
                owner="kumari-anushka",
                name="trace",
            )
    finally:
        await http_client.aclose()


@pytest.mark.asyncio
async def test_get_branch_head_raises_for_invalid_schema() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={},
            request=request,
        )

    github_client, http_client = create_github_client(handler)

    try:
        with pytest.raises(
            GitHubAPIError,
            match="GitHub returned an invalid commit response",
        ):
            await github_client.get_branch_head(
                owner="kumari-anushka",
                name="trace",
                branch="main",
            )
    finally:
        await http_client.aclose()
