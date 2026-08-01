from datetime import UTC, datetime
from uuid import uuid4

from src.ingestion.models import (
    IngestionJob,
    IngestionJobStatus,
    IngestionStage,
    IngestionStageStatus,
)
from src.ingestion.schemas import IngestionJobResponse, IngestionStageResponse


def make_ingestion_job(
    *,
    status: IngestionJobStatus = IngestionJobStatus.RUNNING,
    progress: int = 45,
) -> IngestionJob:
    now = datetime.now(UTC)

    ingestion_job = IngestionJob(
        repository_version_id=uuid4(),
        status=status,
        progress=progress,
    )

    ingestion_job.id = uuid4()
    ingestion_job.created_at = now
    ingestion_job.updated_at = now
    ingestion_job.started_at = now
    ingestion_job.completed_at = None
    ingestion_job.error_message = None

    return ingestion_job


def test_ingestion_job_response_builds_from_model() -> None:
    ingestion_job = make_ingestion_job()

    response = IngestionJobResponse.model_validate(
        ingestion_job,
    )

    assert response.id == ingestion_job.id


def test_ingestion_stage_response_builds_from_model() -> None:
    now = datetime.now(UTC)
    ingestion_stage = IngestionStage(
        ingestion_job_id=uuid4(),
        name="prepare",
        position=0,
        status=IngestionStageStatus.RUNNING,
        progress=25,
    )
    ingestion_stage.id = uuid4()
    ingestion_stage.created_at = now
    ingestion_stage.updated_at = now
    ingestion_stage.started_at = now
    ingestion_stage.completed_at = None
    ingestion_stage.error_message = None

    response = IngestionStageResponse.model_validate(
        ingestion_stage,
    )

    assert response.id == ingestion_stage.id
    assert response.name == "prepare"
    assert response.status is IngestionStageStatus.RUNNING
    assert response.progress == 25
