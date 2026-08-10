from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from src.ask.dependencies import get_repository_query_service
from src.ask.schemas import RepositoryQueryRequest, RepositoryQueryResponse
from src.ask.service import RepositoryQueryService

router = APIRouter(prefix="/repositories", tags=["Repository query"])

RepositoryQueryServiceDependency = Annotated[
    RepositoryQueryService, Depends(get_repository_query_service)
]


@router.post("/{repository_id}/query", response_model=RepositoryQueryResponse)
async def query_repository(
    repository_id: UUID,
    payload: RepositoryQueryRequest,
    service: RepositoryQueryServiceDependency,
) -> RepositoryQueryResponse:
    result = await service.query(repository_id=repository_id, question=payload.question)
    return RepositoryQueryResponse.from_result(result)
