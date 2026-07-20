from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.ingestion.schemas import IngestionJobResponse
from src.repositories.dependencies import (
    get_repository_import_service,
    get_repository_service,
)
from src.repositories.import_service import RepositoryImportService
from src.repositories.schemas import (
    MessageResponse,
    RepositoryImportRequest,
    RepositoryImportResponse,
    RepositoryListResponse,
    RepositoryResponse,
)
from src.repositories.service import RepositoryService
from src.repository_versions.schemas import RepositoryVersionResponse

router = APIRouter(
    prefix="/repositories",
    tags=["Repositories"],
)


RepositoryServiceDependency = Annotated[
    RepositoryService,
    Depends(get_repository_service),
]

RepositoryImportServiceDependency = Annotated[
    RepositoryImportService,
    Depends(get_repository_import_service),
]


@router.post(
    "",
    response_model=RepositoryImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_repository(
    payload: RepositoryImportRequest,
    service: RepositoryImportServiceDependency,
) -> RepositoryImportResponse:
    result = await service.import_repository(
        github_url=str(payload.github_url),
    )

    return RepositoryImportResponse(
        repository=RepositoryResponse.model_validate(
            result.repository,
        ),
        repository_version=RepositoryVersionResponse.model_validate(
            result.repository_version,
        ),
        ingestion_job=IngestionJobResponse.model_validate(
            result.ingestion_job,
        ),
    )


@router.get(
    "",
    response_model=RepositoryListResponse,
)
async def list_repositories(
    service: RepositoryServiceDependency,
) -> RepositoryListResponse:
    repositories = await service.list_repositories()

    return RepositoryListResponse(
        repositories=[RepositoryResponse.model_validate(repository) for repository in repositories],
    )


@router.get(
    "/{repository_id}",
    response_model=RepositoryResponse,
)
async def get_repository(
    repository_id: UUID,
    service: RepositoryServiceDependency,
) -> RepositoryResponse:
    repository = await service.get_repository(repository_id)

    return RepositoryResponse.model_validate(repository)


@router.delete(
    "/{repository_id}",
    response_model=MessageResponse,
)
async def delete_repository(
    repository_id: UUID,
    service: RepositoryServiceDependency,
) -> MessageResponse:
    await service.delete_repository(repository_id)

    return MessageResponse(
        message="Repository deleted successfully",
    )
