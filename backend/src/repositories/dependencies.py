from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dependencies import get_session
from src.github.client import GitHubClient
from src.github.dependencies import get_github_client
from src.ingestion.dependencies import get_ingestion_queue
from src.ingestion.queue import IngestionQueue
from src.ingestion.service import IngestionService
from src.ingestion.store import IngestionJobStore
from src.repositories.import_service import RepositoryImportService
from src.repositories.service import RepositoryService
from src.repositories.store import RepositoryStore
from src.repository_versions.store import RepositoryVersionStore

SessionDependency = Annotated[
    AsyncSession,
    Depends(get_session),
]

GitHubClientDependency = Annotated[
    GitHubClient,
    Depends(get_github_client),
]

IngestionQueueDependency = Annotated[
    IngestionQueue,
    Depends(get_ingestion_queue),
]


def get_repository_service(
    session: SessionDependency,
) -> RepositoryService:
    repository_store = RepositoryStore(
        session=session,
    )

    return RepositoryService(
        session=session,
        store=repository_store,
    )


def get_repository_import_service(
    session: SessionDependency,
    github_client: GitHubClientDependency,
    ingestion_queue: IngestionQueueDependency,
) -> RepositoryImportService:
    repository_store = RepositoryStore(
        session=session,
    )

    repository_version_store = RepositoryVersionStore(
        session=session,
    )

    ingestion_job_store = IngestionJobStore(
        session=session,
    )

    ingestion_service = IngestionService(
        store=ingestion_job_store,
    )

    return RepositoryImportService(
        session=session,
        github_client=github_client,
        repository_store=repository_store,
        repository_version_store=repository_version_store,
        ingestion_service=ingestion_service,
        ingestion_queue=ingestion_queue,
    )
