from fastapi import APIRouter, HTTPException, status

from src.core.exceptions import (
    InvalidGitHubRepositoryURLError,
    RepositoryAlreadyExistsError,
)
from src.db.dependencies import DatabaseSession
from src.models.repository import Repository
from src.schemas.repository import RepositoryCreate, RepositoryResponse
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
    except InvalidGitHubRepositoryURLError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid GitHub repository URL",
        ) from None
    except RepositoryAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Repository already exists",
        ) from None
