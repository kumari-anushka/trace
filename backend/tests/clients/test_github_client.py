import httpx
import pytest
from pydantic import SecretStr

from src.clients.github_client import GitHubClient


@pytest.mark.asyncio
async def test_get_repository_returns_repository_data() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/repos/kumari-anushka/trace"

        assert request.headers["accept"] == "application/vnd.github+json"
        assert request.headers["x-github-api-version"] == "2022-11-28"

        return httpx.Response(
            status_code=200,
            json={
                "id": 123,
                "name": "trace",
                "full_name": "kumari-anushka/trace",
                "default_branch": "main",
                "private": False,
            },
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        base_url="https://api.github.com",
        transport=transport,
    ) as client:
        github_client = GitHubClient(client=client)

        result = await github_client.get_repository(
            owner="kumari-anushka",
            name="trace",
        )

    assert result.id == 123
    assert result.name == "trace"
    assert result.full_name == "kumari-anushka/trace"
    assert result.default_branch == "main"
    assert result.private is False


@pytest.mark.asyncio
async def test_get_repository_raises_when_repository_not_found() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=404,
            json={"message": "Not Found"},
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        base_url="https://api.github.com",
        transport=transport,
    ) as client:
        github_client = GitHubClient(client=client)

        with pytest.raises(httpx.HTTPStatusError) as error:
            await github_client.get_repository(
                owner="missing",
                name="repo",
            )

    assert error.value.response.status_code == 404


@pytest.mark.asyncio
async def test_get_repository_sends_github_token() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-token"

        return httpx.Response(
            status_code=200,
            json={
                "id": 1,
                "name": "trace",
                "full_name": "kumari-anushka/trace",
                "default_branch": "main",
                "private": False,
            },
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        base_url="https://api.github.com",
        transport=transport,
    ) as client:
        github_client = GitHubClient(
            client=client,
            github_token=SecretStr("test-token"),
        )

        result = await github_client.get_repository(
            owner="kumari-anushka",
            name="trace",
        )

    assert result.id == 1
