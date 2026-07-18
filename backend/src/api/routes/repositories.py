from fastapi import APIRouter, HTTPException, status

from src.core.exceptions import (
    InvalidGitHubRepositoryURLError,
    RepositoryAlreadyExistsError,
    RepositoryNotFoundError,
)
from src.db.dependencies import DatabaseSession
from src.models.repository import Repository
from src.schemas.repository import RepositoryCreate, RepositoryDeleteResponse, RepositoryResponse
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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
