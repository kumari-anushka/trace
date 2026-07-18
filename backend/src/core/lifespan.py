from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.cache.redis import redis_client
from src.core.http import create_github_http_client
from src.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    github_http_client = create_github_http_client()
    app.state.github_http_client = github_http_client

    try:
        yield
    finally:
        await github_http_client.aclose()
        await redis_client.aclose()
        await engine.dispose()
