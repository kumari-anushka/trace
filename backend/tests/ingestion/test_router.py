from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.exceptions import IngestionJobNotFoundError
from src.ingestion.dependencies import get_ingestion_service
from src.ingestion.models import IngestionJob, IngestionJobStatus
from src.ingestion.service import IngestionService


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


def override_ingestion_service(
    app: FastAPI,
    service: AsyncMock,
) -> None:
    def dependency_override() -> IngestionService:
        return cast(IngestionService, service)

    app.dependency_overrides[get_ingestion_service] = dependency_override


def test_get_ingestion_job_returns_job(
    app: FastAPI,
    client: TestClient,
) -> None:
    ingestion_job = make_ingestion_job()

    service = AsyncMock(spec=IngestionService)
    service.get_job.return_value = ingestion_job

    override_ingestion_service(app, service)

    response = client.get(
        f"/ingestion-jobs/{ingestion_job.id}",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == str(ingestion_job.id)
    assert body["repository_version_id"] == str(
        ingestion_job.repository_version_id,
    )
    assert body["status"] == "running"
    assert body["progress"] == 45
    assert body["error_message"] is None
    assert body["started_at"] is not None
    assert body["completed_at"] is None

    service.get_job.assert_awaited_once_with(
        ingestion_job.id,
    )


def test_get_ingestion_job_returns_failed_job(
    app: FastAPI,
    client: TestClient,
) -> None:
    ingestion_job = make_ingestion_job(
        status=IngestionJobStatus.FAILED,
        progress=20,
    )
    ingestion_job.error_message = "Clone failed"
    ingestion_job.completed_at = datetime.now(UTC)

    service = AsyncMock(spec=IngestionService)
    service.get_job.return_value = ingestion_job

    override_ingestion_service(app, service)

    response = client.get(
        f"/ingestion-jobs/{ingestion_job.id}",
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "failed"
    assert body["progress"] == 20
    assert body["error_message"] == "Clone failed"
    assert body["completed_at"] is not None


def test_get_ingestion_job_returns_404_when_missing(
    app: FastAPI,
    client: TestClient,
) -> None:
    ingestion_job_id = uuid4()

    service = AsyncMock(spec=IngestionService)
    service.get_job.side_effect = IngestionJobNotFoundError()

    override_ingestion_service(app, service)

    response = client.get(
        f"/ingestion-jobs/{ingestion_job_id}",
    )

    assert response.status_code == 404
    assert response.json() == {
        "message": "Ingestion job not found",
    }

    service.get_job.assert_awaited_once_with(
        ingestion_job_id,
    )


def test_get_ingestion_job_returns_422_for_invalid_uuid(
    app: FastAPI,
    client: TestClient,
) -> None:
    service = AsyncMock(spec=IngestionService)

    override_ingestion_service(app, service)

    response = client.get(
        "/ingestion-jobs/not-a-uuid",
    )

    assert response.status_code == 422
    assert response.json()["message"] == "Invalid request"

    service.get_job.assert_not_awaited()
