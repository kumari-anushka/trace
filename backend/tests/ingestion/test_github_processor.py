from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.github.client import GitHubClient
from src.github.schemas import GitHubCommit, GitHubRepository, GitHubTree
from src.github.store import GitHubArtifactStore
from src.ingestion.models import (
    IngestionJob,
    IngestionJobStatus,
    IngestionStage,
    IngestionStageStatus,
)
from src.ingestion.processor import (
    ARTIFACTS_STAGE_NAME,
    METADATA_STAGE_NAME,
    SOURCE_TREE_STAGE_NAME,
    GitHubIngestionLimits,
    GitHubIngestionProcessor,
)
from src.ingestion.service import IngestionService, IngestionStageService
from src.repositories.models import Repository
from src.repositories.service import RepositoryService
from src.repository_versions.models import RepositoryVersion
from src.repository_versions.service import RepositoryVersionService

SNAPSHOT_SHA = "a" * 40
TREE_SHA = "f" * 40


@pytest.mark.asyncio
async def test_processor_anchors_every_snapshot_call_to_submission_sha() -> None:
    now = datetime.now(UTC)
    repository = Repository(
        github_id=123,
        github_url="https://github.com/acme/trace",
        owner="acme",
        name="trace",
        default_branch="main",
    )
    repository.id = uuid4()
    version = RepositoryVersion(
        repository_id=repository.id,
        commit_sha=SNAPSHOT_SHA,
        branch="main",
    )
    version.id = uuid4()
    job = IngestionJob(
        repository_version_id=version.id,
        status=IngestionJobStatus.RUNNING,
        progress=0,
    )
    job.id = uuid4()

    stages = []
    for position, name in enumerate(
        (METADATA_STAGE_NAME, SOURCE_TREE_STAGE_NAME, ARTIFACTS_STAGE_NAME)
    ):
        stage = IngestionStage(
            ingestion_job_id=job.id,
            name=name,
            position=position,
            status=IngestionStageStatus.PENDING,
            progress=0,
        )
        stage.id = uuid4()
        stage.created_at = now
        stage.updated_at = now
        stages.append(stage)

    session = AsyncMock(spec=AsyncSession)
    ingestion_service = AsyncMock(spec=IngestionService)
    stage_service = AsyncMock(spec=IngestionStageService)
    version_service = AsyncMock(spec=RepositoryVersionService)
    repository_service = AsyncMock(spec=RepositoryService)
    github_client = AsyncMock(spec=GitHubClient)
    artifact_store = AsyncMock(spec=GitHubArtifactStore)

    stage_service.list_stages.return_value = []
    stage_service.create_stage.side_effect = stages
    version_service.get_repository_version.return_value = version
    repository_service.get_repository.return_value = repository
    github_client.get_repository.return_value = GitHubRepository.model_validate(
        {
            "id": 123,
            "name": "trace",
            "full_name": "acme/trace",
            "html_url": "https://github.com/acme/trace",
            "default_branch": "main",
            "private": False,
            "archived": False,
            "disabled": False,
            "owner": {"id": 1, "login": "acme"},
        }
    )
    github_client.get_commit.return_value = GitHubCommit.model_validate(
        {
            "sha": SNAPSHOT_SHA,
            "commit": {"tree": {"sha": TREE_SHA}},
        }
    )
    github_client.get_languages.return_value = {"Python": 100}
    github_client.get_complete_tree.return_value = GitHubTree(
        sha=TREE_SHA,
        truncated=False,
        tree=[],
    )
    github_client.list_labels.return_value = []
    github_client.list_issues.return_value = []
    github_client.list_pull_requests.return_value = []
    github_client.list_commits.return_value = []
    github_client.list_releases.return_value = []
    github_client.list_contributors.return_value = []
    artifact_store.replace_source_tree.return_value = {"files": 0}
    artifact_store.persist_artifacts.return_value = {"commits": 0}

    def mark_running(stage: IngestionStage) -> IngestionStage:
        stage.status = IngestionStageStatus.RUNNING
        return stage

    def mark_completed(
        stage: IngestionStage,
        *,
        output_summary: dict[str, object] | None = None,
    ) -> IngestionStage:
        stage.status = IngestionStageStatus.COMPLETED
        stage.output_summary = output_summary
        return stage

    stage_service.mark_running.side_effect = mark_running
    stage_service.mark_completed.side_effect = mark_completed

    processor = GitHubIngestionProcessor(
        session=session,
        ingestion_service=ingestion_service,
        stage_service=stage_service,
        repository_version_service=version_service,
        repository_service=repository_service,
        github_client=github_client,
        artifact_store=artifact_store,
        limits=GitHubIngestionLimits(),
    )

    await processor.process(job)

    github_client.get_commit.assert_awaited_once_with(
        owner="acme",
        name="trace",
        ref=SNAPSHOT_SHA,
    )
    github_client.get_complete_tree.assert_awaited_once_with(
        owner="acme",
        name="trace",
        tree_sha=TREE_SHA,
    )
    assert github_client.list_commits.await_args.kwargs["snapshot_sha"] == SNAPSHOT_SHA
    assert [stage.status for stage in stages] == [
        IngestionStageStatus.COMPLETED,
        IngestionStageStatus.COMPLETED,
        IngestionStageStatus.COMPLETED,
    ]
