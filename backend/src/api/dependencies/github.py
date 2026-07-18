from typing import Annotated

import httpx
from fastapi import Depends, Request

from src.clients.github_client import GitHubClient


def get_github_http_client(
    request: Request,
) -> httpx.AsyncClient:
    client: httpx.AsyncClient = request.app.state.github_http_client
    return client


def get_github_client(
    request: Request,
) -> GitHubClient:
    return GitHubClient(
        client=get_github_http_client(request),
    )


GithubSession = Annotated[
    GitHubClient,
    Depends(get_github_client),
]
