from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from src.ingestion.dependencies import get_ingestion_service
from src.ingestion.schemas import IngestionJobResponse
from src.ingestion.service import IngestionService

router = APIRouter(
    prefix="/ingestion-jobs",
    tags=["Ingestion Jobs"],
)


IngestionServiceDependency = Annotated[
    IngestionService,
    Depends(get_ingestion_service),
]


@router.get(
    "/{ingestion_job_id}",
    response_model=IngestionJobResponse,
)
async def get_ingestion_job(
    ingestion_job_id: UUID,
    service: IngestionServiceDependency,
) -> IngestionJobResponse:
    ingestion_job = await service.get_job(
        ingestion_job_id,
    )

    return IngestionJobResponse.model_validate(
        ingestion_job,
    )
