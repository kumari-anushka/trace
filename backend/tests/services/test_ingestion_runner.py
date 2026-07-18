from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.github_client import GitHubClient
from src.models.enums import IngestionJobStatus
from src.services.ingestion_runner import IngestionRunner


def create_runner() -> IngestionRunner:
    session = AsyncMock(spec=AsyncSession)
    http_client = AsyncMock(spec=httpx.AsyncClient)

    github_client = GitHubClient(
        client=http_client,
    )

    return IngestionRunner(
        session,
        github_client=github_client,
    )


@pytest.mark.asyncio
async def test_run_marks_job_running_then_completed() -> None:
    runner = create_runner()

    with (
        patch.object(
            runner.ingestion_service,
            "update_ingestion_job",
            new=AsyncMock(),
        ) as update_job_mock,
        patch.object(
            runner,
            "_ingest",
            new=AsyncMock(),
        ) as ingest_mock,
    ):
        await runner.run(
            job_id=1,
            owner="kumari-anushka",
            name="trace",
        )

    ingest_mock.assert_awaited_once_with(
        owner="kumari-anushka",
        name="trace",
    )

    assert update_job_mock.await_args_list[0].kwargs == {
        "job_id": 1,
        "status": IngestionJobStatus.RUNNING,
        "progress": 10,
    }

    assert update_job_mock.await_args_list[1].kwargs == {
        "job_id": 1,
        "status": IngestionJobStatus.COMPLETED,
        "progress": 100,
    }


@pytest.mark.asyncio
async def test_run_marks_job_failed_when_ingestion_fails() -> None:
    runner = create_runner()

    with (
        patch.object(
            runner.ingestion_service,
            "update_ingestion_job",
            new=AsyncMock(),
        ) as update_job_mock,
        patch.object(
            runner,
            "_ingest",
            new=AsyncMock(
                side_effect=RuntimeError("clone failed"),
            ),
        ),
    ):
        with pytest.raises(RuntimeError, match="clone failed"):
            await runner.run(
                job_id=1,
                owner="kumari-anushka",
                name="trace",
            )

    assert update_job_mock.await_args_list[1].kwargs == {
        "job_id": 1,
        "status": IngestionJobStatus.FAILED,
        "progress": 10,
        "error_message": "clone failed",
    }


@pytest.mark.asyncio
async def test_run_preserves_original_error_when_failure_update_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runner = create_runner()

    update_job_mock = AsyncMock(
        side_effect=[
            None,
            RuntimeError("database unavailable"),
        ]
    )

    with (
        patch.object(
            runner.ingestion_service,
            "update_ingestion_job",
            new=update_job_mock,
        ),
        patch.object(
            runner,
            "_ingest",
            new=AsyncMock(
                side_effect=RuntimeError("clone failed"),
            ),
        ),
    ):
        with pytest.raises(RuntimeError, match="clone failed"):
            await runner.run(
                job_id=1,
                owner="kumari-anushka",
                name="trace",
            )

    assert "Failed to mark ingestion job 1 as failed" in caplog.text
