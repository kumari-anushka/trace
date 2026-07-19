from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies.repository import (
    get_repository_creation_service,
    get_repository_service,
)
from src.core.exceptions import (
    IngestionJobNotFoundError,
    InvalidGitHubRepositoryURLError,
    RepositoryAlreadyExistsError,
    RepositoryNotFoundError,
    SnapshotAlreadyExistsError,
)
from src.db.dependencies import DatabaseSession
from src.models.repository import Repository
from src.schemas.ingestion import IngestionJobResponse
from src.schemas.repository import (
    RepositoryCreate,
    RepositoryDeleteResponse,
    RepositoryResponse,
)
from src.services.ingestion_service import IngestionService
from src.services.repository_creation_service import (
    RepositoryCreationService,
)
from src.services.repository_service import RepositoryService

router = APIRouter(
    prefix="/repositories",
    tags=["Repositories"],
)


@router.post(
    "",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_repository(
    payload: RepositoryCreate,
    service: Annotated[
        RepositoryCreationService,
        Depends(get_repository_creation_service),
    ],
) -> Repository:
    try:
        return await service.create_repository(
            github_url=str(payload.github_url),
        )
    except InvalidGitHubRepositoryURLError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid GitHub repository URL",
        ) from exc
    except RepositoryAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository already exists",
        ) from exc
    except SnapshotAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Snapshot already exists",
        ) from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=("GitHub repository does not exist or is not publicly accessible"),
            ) from exc

        if exc.response.status_code == status.HTTP_403_FORBIDDEN:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="GitHub API request forbidden or rate limited",
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub API request failed",
        ) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="GitHub API request timed out",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not connect to GitHub API",
        ) from exc


@router.get(
    "",
    response_model=list[RepositoryResponse],
    status_code=status.HTTP_200_OK,
)
async def list_repositories(
    service: Annotated[
        RepositoryService,
        Depends(get_repository_service),
    ],
) -> list[RepositoryResponse]:
    repositories = await service.list_repositories()

    return [RepositoryResponse.model_validate(repository) for repository in repositories]


@router.delete(
    "/{repository_id}",
    status_code=status.HTTP_200_OK,
)
async def delete_repository(
    repository_id: int,
    service: Annotated[
        RepositoryService,
        Depends(get_repository_service),
    ],
) -> RepositoryDeleteResponse:
    try:
        await service.delete_repository(
            repository_id=repository_id,
        )
    except RepositoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        ) from exc

    return RepositoryDeleteResponse(
        message="Repository deleted successfully",
    )


@router.get(
    "/{repository_id}/ingestions/{job_id}",
    response_model=IngestionJobResponse,
)
async def get_ingestion_job(
    repository_id: int,
    job_id: int,
    session: DatabaseSession,
) -> IngestionJobResponse:
    service = IngestionService(session)

    try:
        job = await service.get_ingestion_job(
            repository_id=repository_id,
            job_id=job_id,
        )
    except IngestionJobNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion job not found",
        ) from error

    return IngestionJobResponse.model_validate(job)
