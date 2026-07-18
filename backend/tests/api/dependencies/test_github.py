from unittest.mock import MagicMock

import httpx
from fastapi import FastAPI, Request

from src.api.dependencies.github import (
    get_github_client,
    get_github_http_client,
)


def test_get_github_http_client_returns_app_client() -> None:
    client = MagicMock(spec=httpx.AsyncClient)

    app = FastAPI()
    app.state.github_http_client = client

    request = MagicMock(spec=Request)
    request.app = app

    result = get_github_http_client(request)

    assert result is client


def test_get_github_client_uses_app_http_client() -> None:
    client = MagicMock(spec=httpx.AsyncClient)

    app = FastAPI()
    app.state.github_http_client = client

    request = MagicMock(spec=Request)
    request.app = app

    result = get_github_client(request)

    assert result.client is client
