import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from src.core.exceptions import GitHubAPIError, GitHubRateLimitError
from src.github.client import GitHubClient

FIXTURES = Path(__file__).parents[1] / "fixtures" / "github"


def load_fixture(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


@pytest.mark.asyncio
async def test_issue_pagination_uses_fixtures_and_filters_pull_requests() -> None:
    requested_pages: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params.get("page")
        requested_pages.append(page)
        if page == "2":
            return httpx.Response(200, json=load_fixture("issues_page_2.json"))
        return httpx.Response(
            200,
            json=load_fixture("issues_page_1.json"),
            headers={
                "Link": (
                    "<https://api.github.test/repos/acme/trace/issues?page=2&per_page=100>; "
                    'rel="next"'
                )
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = GitHubClient(
        http_client=http_client,
        api_url="https://api.github.test",
        token=None,
        max_retries=0,
    )
    try:
        issues = await client.list_issues(owner="acme", name="trace", limit=100)
    finally:
        await http_client.aclose()

    assert requested_pages == [None, "2"]
    assert [issue.number for issue in issues] == [12]
    assert issues[0].labels[0].name == "ingestion"


@pytest.mark.asyncio
async def test_rate_limit_retries_after_provider_delay() -> None:
    attempts = 0
    sleep = AsyncMock()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "2"},
                request=request,
            )
        return httpx.Response(200, json={"Python": 100}, request=request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = GitHubClient(
        http_client=http_client,
        api_url="https://api.github.test",
        token=None,
        max_retries=1,
        sleep=sleep,
    )
    try:
        languages = await client.get_languages(owner="acme", name="trace")
    finally:
        await http_client.aclose()

    assert languages == {"Python": 100}
    assert attempts == 2
    sleep.assert_awaited_once_with(2.0)


@pytest.mark.asyncio
async def test_rate_limit_exhaustion_is_explicitly_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "9999999999"},
            request=request,
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = GitHubClient(
        http_client=http_client,
        api_url="https://api.github.test",
        token=None,
        max_retries=0,
    )
    try:
        with pytest.raises(GitHubRateLimitError) as raised:
            await client.get_languages(owner="acme", name="trace")
    finally:
        await http_client.aclose()

    assert raised.value.retry_after_seconds is not None


@pytest.mark.asyncio
async def test_truncated_tree_falls_back_to_non_recursive_walk() -> None:
    root_sha = "a" * 40
    subtree_sha = "b" * 40
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        if request.url.path.endswith(f"/{subtree_sha}"):
            return httpx.Response(
                200,
                json={
                    "sha": subtree_sha,
                    "truncated": False,
                    "tree": [
                        {
                            "path": "main.py",
                            "mode": "100644",
                            "type": "blob",
                            "sha": "c" * 40,
                            "size": 20,
                        }
                    ],
                },
            )
        if request.url.params.get("recursive") == "1":
            return httpx.Response(
                200,
                json={"sha": root_sha, "truncated": True, "tree": []},
            )
        return httpx.Response(
            200,
            json={
                "sha": root_sha,
                "truncated": False,
                "tree": [
                    {
                        "path": "src",
                        "mode": "040000",
                        "type": "tree",
                        "sha": subtree_sha,
                    }
                ],
            },
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = GitHubClient(
        http_client=http_client,
        api_url="https://api.github.test",
        token=None,
        max_retries=0,
    )
    try:
        tree = await client.get_complete_tree(
            owner="acme",
            name="trace",
            tree_sha=root_sha,
        )
    finally:
        await http_client.aclose()

    assert tree.truncated is False
    assert [entry.path for entry in tree.tree] == ["src", "src/main.py"]
    assert len(requested_urls) == 3


@pytest.mark.asyncio
async def test_download_snapshot_archive_uses_fixed_commit_sha() -> None:
    archive = b"PK-test-archive"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith(f"/zipball/{'a' * 40}")
        return httpx.Response(200, content=archive, request=request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = GitHubClient(
        http_client=http_client,
        api_url="https://api.github.test",
        token=None,
        max_retries=0,
    )
    try:
        result = await client.download_snapshot_archive(
            owner="acme",
            name="trace",
            commit_sha="a" * 40,
            max_bytes=100,
        )
    finally:
        await http_client.aclose()

    assert result == archive


@pytest.mark.asyncio
async def test_download_snapshot_archive_enforces_size_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"too-large", request=request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = GitHubClient(
        http_client=http_client,
        api_url="https://api.github.test",
        token=None,
        max_retries=0,
    )
    try:
        with pytest.raises(GitHubAPIError, match="archive exceeds"):
            await client.download_snapshot_archive(
                owner="acme",
                name="trace",
                commit_sha="a" * 40,
                max_bytes=5,
            )
    finally:
        await http_client.aclose()
