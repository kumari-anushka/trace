from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from src.repository_versions.dependencies import (
    get_repository_version_service,
)
from src.repository_versions.schemas import (
    RepositoryVersionResponse,
)
from src.repository_versions.service import (
    RepositoryVersionService,
)

router = APIRouter(
    prefix="/repository-versions",
    tags=["Repository Versions"],
)


RepositoryVersionServiceDependency = Annotated[
    RepositoryVersionService,
    Depends(get_repository_version_service),
]


@router.get(
    "",
    response_model=list[RepositoryVersionResponse],
)
async def list_repository_versions(
    repository_id: UUID,
    service: RepositoryVersionServiceDependency,
) -> list[RepositoryVersionResponse]:
    repository_versions = await service.list_repository_versions(
        repository_id,
    )

    return [
        RepositoryVersionResponse.model_validate(repository_version)
        for repository_version in repository_versions
    ]


@router.get(
    "/{repository_version_id}",
    response_model=RepositoryVersionResponse,
)
async def get_repository_version(
    repository_version_id: UUID,
    service: RepositoryVersionServiceDependency,
) -> RepositoryVersionResponse:
    repository_version = await service.get_repository_version(
        repository_version_id,
    )

    return RepositoryVersionResponse.model_validate(
        repository_version,
    )
