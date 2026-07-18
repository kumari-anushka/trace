from collections.abc import AsyncGenerator
from typing import Annotated

import httpx
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.github_client import GitHubClient
from src.core.config import settings
from src.db.session import get_db_session
from src.services.ingestion_coordinator import IngestionCoordinator


async def get_github_client() -> AsyncGenerator[GitHubClient]:
    async with httpx.AsyncClient(
        base_url="https://api.github.com",
        timeout=20.0,
    ) as http_client:
        yield GitHubClient(
            client=http_client,
            github_token=settings.github_token,
        )


def get_ingestion_coordinator(
    session: Annotated[
        AsyncSession,
        Depends(get_db_session),
    ],
    github_client: Annotated[
        GitHubClient,
        Depends(get_github_client),
    ],
) -> IngestionCoordinator:
    return IngestionCoordinator(
        session,
        github_client=github_client,
    )
