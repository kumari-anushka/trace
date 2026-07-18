from fastapi import APIRouter, HTTPException, status

from src.core.exceptions import (
    IngestionJobNotFoundError,
    InvalidGitHubRepositoryURLError,
    RepositoryAlreadyExistsError,
    RepositoryNotFoundError,
    SnapshotAlreadyExistsError,
)
from src.db.dependencies import DatabaseSession
from src.models.repository import Repository
from src.schemas.ingestion import (
    IngestionCreate,
    IngestionJobResponse,
    IngestionResponse,
    RepositorySnapshotResponse,
)
from src.schemas.repository import RepositoryCreate, RepositoryDeleteResponse, RepositoryResponse
from src.services.ingestion_service import IngestionService
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
    session: DatabaseSession,
) -> Repository:
    service = RepositoryService(session)

    try:
        return await service.create_repository(
            github_url=str(payload.github_url),
            default_branch=payload.default_branch,
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


@router.get("", response_model=list[RepositoryResponse], status_code=status.HTTP_200_OK)
async def list_repositories(session: DatabaseSession) -> list[RepositoryResponse]:
    service = RepositoryService(session)
    repositories = await service.list_repositories()

    return [RepositoryResponse.model_validate(repository) for repository in repositories]


@router.delete("/{repository_id}", status_code=status.HTTP_200_OK)
async def delete_repository(
    repository_id: int, session: DatabaseSession
) -> RepositoryDeleteResponse:
    service = RepositoryService(session)
    try:
        await service.delete_repository(repository_id=repository_id)
    except RepositoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        ) from exc
    return RepositoryDeleteResponse(message="Repository deleted successfully")


@router.post(
    "/{repository_id}/ingestions",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ingestion(
    repository_id: int,
    payload: IngestionCreate,
    session: DatabaseSession,
) -> IngestionResponse:
    repository_service = RepositoryService(session)
    repository = await repository_service.get_repository(repository_id)

    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    ingestion_service = IngestionService(session)

    try:
        snapshot, job = await ingestion_service.create_ingestion(
            repository,
            commit_sha=payload.commit_sha,
            default_branch=payload.default_branch,
        )
    except SnapshotAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Snapshot already exists",
        ) from error

    return IngestionResponse(
        snapshot=RepositorySnapshotResponse.model_validate(snapshot),
        job=IngestionJobResponse.model_validate(job),
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
