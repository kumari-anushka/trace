from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from src.api.exception_handlers import register_exception_handlers
from src.api.router import api_router
from src.core.config import get_settings


@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncIterator[None]:
    settings = get_settings()

    github_http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0),
        follow_redirects=False,
    )

    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )

    app.state.github_http_client = github_http_client
    app.state.redis_client = redis_client

    try:
        yield
    finally:
        await github_http_client.aclose()
        await redis_client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=[
            "GET",
            "POST",
            "DELETE",
            "OPTIONS",
        ],
        allow_headers=[
            "Content-Type",
        ],
    )

    register_exception_handlers(app)
    app.include_router(api_router)

    return app


app = create_app()
