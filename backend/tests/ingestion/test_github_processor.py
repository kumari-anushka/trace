from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import AsyncMock
from uuid import uuid4
from zipfile import ZipFile

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.github.client import GitHubClient
from src.github.schemas import GitHubCommit, GitHubPullRequest, GitHubRepository, GitHubTree
from src.github.store import GitHubArtifactStore
from src.ingestion.models import (
    IngestionJob,
    IngestionJobStatus,
    IngestionStage,
    IngestionStageStatus,
)
from src.ingestion.processor import (
    ARTIFACTS_STAGE_NAME,
    COMMITS_STAGE_NAME,
    ISSUES_STAGE_NAME,
    METADATA_STAGE_NAME,
    PULL_REQUESTS_STAGE_NAME,
    SOURCE_CONTENTS_STAGE_NAME,
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


def empty_snapshot_archive() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("acme-trace/", "")
    return buffer.getvalue()


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
        (
            METADATA_STAGE_NAME,
            SOURCE_TREE_STAGE_NAME,
            SOURCE_CONTENTS_STAGE_NAME,
            ISSUES_STAGE_NAME,
            PULL_REQUESTS_STAGE_NAME,
            COMMITS_STAGE_NAME,
            ARTIFACTS_STAGE_NAME,
        )
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
    github_client.download_snapshot_archive.return_value = empty_snapshot_archive()
    artifact_store.replace_source_tree.return_value = {"files": 0}
    artifact_store.list_content_candidate_paths.return_value = set()
    artifact_store.replace_source_contents.return_value = {"contents": 0}
    artifact_store.persist_labels_and_issues.return_value = {"labels": 0, "issues": 0}
    artifact_store.persist_releases_and_contributors.return_value = {
        "releases": 0,
        "contributors": 0,
    }

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
        IngestionStageStatus.COMPLETED,
        IngestionStageStatus.COMPLETED,
        IngestionStageStatus.COMPLETED,
        IngestionStageStatus.COMPLETED,
    ]


@pytest.mark.asyncio
async def test_pull_request_checkpoint_skips_already_persisted_items() -> None:
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
        progress=60,
    )
    job.id = uuid4()

    stage_names = (
        METADATA_STAGE_NAME,
        SOURCE_TREE_STAGE_NAME,
        SOURCE_CONTENTS_STAGE_NAME,
        ISSUES_STAGE_NAME,
        PULL_REQUESTS_STAGE_NAME,
        COMMITS_STAGE_NAME,
        ARTIFACTS_STAGE_NAME,
    )
    stages = []
    for position, name in enumerate(stage_names):
        status = (
            IngestionStageStatus.RUNNING
            if name == PULL_REQUESTS_STAGE_NAME
            else IngestionStageStatus.COMPLETED
        )
        stage = IngestionStage(
            ingestion_job_id=job.id,
            name=name,
            position=position,
            status=status,
            progress=50 if status is IngestionStageStatus.RUNNING else 100,
        )
        stage.id = uuid4()
        stage.created_at = now
        stage.updated_at = now
        if name == PULL_REQUESTS_STAGE_NAME:
            stage.output_summary = {
                "pull_requests": 1,
                "pull_request_files": 2,
                "reviews": 1,
                "_processed_numbers": [1],
                "_total": 2,
            }
        stages.append(stage)

    pull_requests = [
        GitHubPullRequest.model_validate(
            {
                "id": 100 + number,
                "number": number,
                "title": f"PR {number}",
                "state": "open",
                "html_url": f"https://github.test/pull/{number}",
                "head": {"sha": "b" * 40},
                "base": {"sha": "c" * 40},
                "created_at": now,
                "updated_at": now,
            }
        )
        for number in (1, 2)
    ]
    session = AsyncMock(spec=AsyncSession)
    ingestion_service = AsyncMock(spec=IngestionService)
    stage_service = AsyncMock(spec=IngestionStageService)
    version_service = AsyncMock(spec=RepositoryVersionService)
    repository_service = AsyncMock(spec=RepositoryService)
    github_client = AsyncMock(spec=GitHubClient)
    artifact_store = AsyncMock(spec=GitHubArtifactStore)
    stage_service.list_stages.return_value = stages
    version_service.get_repository_version.return_value = version
    repository_service.get_repository.return_value = repository
    github_client.list_pull_requests.return_value = pull_requests
    github_client.list_pull_request_files.return_value = []
    github_client.list_pull_request_reviews.return_value = []
    artifact_store.persist_pull_requests.return_value = {
        "pull_requests": 1,
        "pull_request_files": 0,
        "reviews": 0,
    }

    def update_stage(
        stage: IngestionStage,
        *,
        progress: int,
        output_summary: dict[str, object] | None = None,
    ) -> IngestionStage:
        stage.progress = progress
        stage.output_summary = output_summary
        return stage

    def complete_stage(
        stage: IngestionStage,
        *,
        output_summary: dict[str, object] | None = None,
    ) -> IngestionStage:
        stage.status = IngestionStageStatus.COMPLETED
        stage.output_summary = output_summary
        return stage

    stage_service.update_progress.side_effect = update_stage
    stage_service.mark_completed.side_effect = complete_stage
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

    github_client.list_pull_request_files.assert_awaited_once()
    assert github_client.list_pull_request_files.await_args.kwargs["number"] == 2
    github_client.list_pull_request_reviews.assert_awaited_once()
    persisted_prs = artifact_store.persist_pull_requests.await_args.kwargs["pull_requests"]
    assert [pull_request.number for pull_request in persisted_prs] == [2]
    assert stages[4].status is IngestionStageStatus.COMPLETED
    assert stages[4].output_summary == {
        "pull_requests": 2,
        "pull_request_files": 2,
        "reviews": 1,
    }
