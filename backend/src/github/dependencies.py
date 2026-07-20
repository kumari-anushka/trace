import httpx
from fastapi import Request

from src.core.config import get_settings
from src.github.client import GitHubClient


def get_github_client(
    request: Request,
) -> GitHubClient:
    settings = get_settings()

    http_client: httpx.AsyncClient = request.app.state.github_http_client

    return GitHubClient(
        http_client=http_client,
        api_url=settings.github_api_url,
        token=settings.github_token,
    )
