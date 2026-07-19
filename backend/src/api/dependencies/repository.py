from functools import lru_cache

import httpx

from src.clients.github_client import GitHubClient
from src.db.dependencies import DatabaseSession
from src.services.repository_creation_service import (
    RepositoryCreationService,
)
from src.services.repository_service import RepositoryService


@lru_cache
def get_github_client() -> GitHubClient:
    return GitHubClient(
        client=httpx.AsyncClient(
            base_url="https://api.github.com",
            timeout=10.0,
        ),
    )


def get_repository_service(
    session: DatabaseSession,
) -> RepositoryService:
    return RepositoryService(session)


def get_repository_creation_service(
    session: DatabaseSession,
) -> RepositoryCreationService:
    return RepositoryCreationService(
        session,
        github_client=get_github_client(),
    )
