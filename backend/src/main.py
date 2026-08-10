from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from src.api.exception_handlers import register_exception_handlers
from src.api.router import api_router
from src.core.config import get_settings
from src.health.router import router as health_router


@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncIterator[None]:
    settings = get_settings()

    github_http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0),
        follow_redirects=False,
    )
    openai_http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.openai_timeout_seconds),
        follow_redirects=False,
    )

    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )

    app.state.github_http_client = github_http_client
    app.state.openai_http_client = openai_http_client
    app.state.redis_client = redis_client

    try:
        yield
    finally:
        await github_http_client.aclose()
        await openai_http_client.aclose()
        await redis_client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "Trace turns public GitHub repositories into persistent, "
            "evidence-backed Software Atlases."
        ),
        version="0.1.0",
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
    app.include_router(health_router)
    app.include_router(api_router)

    return app


app = create_app()
