from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    IngestionDispatchError,
    RepositoryAlreadyExistsError,
)
from src.github.client import GitHubClient
from src.github.schemas import (
    GitHubCommit,
    GitHubOwner,
    GitHubRepository,
)
from src.ingestion.models import (
    IngestionJob,
    IngestionJobStatus,
)
from src.ingestion.queue import IngestionQueue
from src.ingestion.service import IngestionService
from src.repositories.import_service import (
    RepositoryImportService,
)
from src.repositories.models import Repository
from src.repositories.store import RepositoryStore
from src.repository_versions.models import RepositoryVersion
from src.repository_versions.store import RepositoryVersionStore

GITHUB_URL = "https://github.com/kumari-anushka/trace"
COMMIT_SHA = "a" * 40


def make_github_repository() -> GitHubRepository:
    return GitHubRepository(
        id=123456789,
        name="trace",
        full_name="kumari-anushka/trace",
        html_url=GITHUB_URL,
        default_branch="main",
        private=False,
        archived=False,
        disabled=False,
        owner=GitHubOwner(
            login="kumari-anushka",
        ),
    )


def make_repository() -> Repository:
    now = datetime.now(UTC)

    repository = Repository(
        github_id=123456789,
        github_url=GITHUB_URL,
        owner="kumari-anushka",
        name="trace",
        default_branch="main",
    )

    repository.id = uuid4()
    repository.created_at = now
    repository.updated_at = now

    return repository


def make_repository_version(
    repository: Repository,
) -> RepositoryVersion:
    repository_version = RepositoryVersion(
        repository_id=repository.id,
        commit_sha=COMMIT_SHA,
        branch="main",
    )

    repository_version.id = uuid4()
    repository_version.created_at = datetime.now(UTC)

    return repository_version


def make_ingestion_job(
    repository_version: RepositoryVersion,
) -> IngestionJob:
    now = datetime.now(UTC)

    ingestion_job = IngestionJob(
        repository_version_id=repository_version.id,
        status=IngestionJobStatus.PENDING,
        progress=0,
    )

    ingestion_job.id = uuid4()
    ingestion_job.created_at = now
    ingestion_job.updated_at = now

    return ingestion_job


def make_service() -> tuple[
    RepositoryImportService,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    session = AsyncMock(spec=AsyncSession)
    github_client = AsyncMock(spec=GitHubClient)
    repository_store = AsyncMock(spec=RepositoryStore)
    repository_version_store = AsyncMock(
        spec=RepositoryVersionStore,
    )
    ingestion_service = AsyncMock(spec=IngestionService)
    ingestion_queue = AsyncMock(spec=IngestionQueue)

    service = RepositoryImportService(
        session=session,
        github_client=github_client,
        repository_store=repository_store,
        repository_version_store=repository_version_store,
        ingestion_service=ingestion_service,
        ingestion_queue=ingestion_queue,
    )

    return (
        service,
        session,
        github_client,
        repository_store,
        repository_version_store,
        ingestion_service,
        ingestion_queue,
    )


@pytest.mark.asyncio
async def test_import_repository_creates_and_dispatches_import() -> None:
    (
        service,
        session,
        github_client,
        repository_store,
        repository_version_store,
        ingestion_service,
        ingestion_queue,
    ) = make_service()

    github_repository = make_github_repository()
    github_commit = GitHubCommit(
        sha=COMMIT_SHA,
    )
    repository = make_repository()
    repository_version = make_repository_version(repository)
    ingestion_job = make_ingestion_job(repository_version)

    github_client.get_repository.return_value = github_repository
    github_client.get_branch_head.return_value = github_commit
    repository_store.get_by_github_id.return_value = None
    repository_store.create.return_value = repository
    repository_version_store.create.return_value = repository_version
    ingestion_service.create_job.return_value = ingestion_job
    ingestion_service.mark_queued.return_value = ingestion_job

    result = await service.import_repository(
        github_url=GITHUB_URL,
    )

    assert result.repository is repository
    assert result.repository_version is repository_version
    assert result.ingestion_job is ingestion_job

    github_client.get_repository.assert_awaited_once_with(
        owner="kumari-anushka",
        name="trace",
    )

    repository_store.get_by_github_id.assert_awaited_once_with(
        github_repository.github_id,
    )

    github_client.get_branch_head.assert_awaited_once_with(
        owner="kumari-anushka",
        name="trace",
        branch="main",
    )

    repository_store.create.assert_awaited_once_with(
        github_id=123456789,
        github_url=GITHUB_URL,
        owner="kumari-anushka",
        name="trace",
        default_branch="main",
    )

    repository_version_store.create.assert_awaited_once_with(
        repository_id=repository.id,
        commit_sha=COMMIT_SHA,
        branch="main",
    )

    ingestion_service.create_job.assert_awaited_once_with(
        repository_version_id=repository_version.id,
    )

    assert session.commit.await_count == 2
    session.rollback.assert_not_awaited()

    ingestion_queue.enqueue.assert_awaited_once_with(
        ingestion_job_id=ingestion_job.id,
    )

    ingestion_service.mark_queued.assert_awaited_once_with(
        ingestion_job,
    )


@pytest.mark.asyncio
async def test_import_repository_rejects_existing_repository() -> None:
    (
        service,
        session,
        github_client,
        repository_store,
        repository_version_store,
        ingestion_service,
        ingestion_queue,
    ) = make_service()

    github_repository = make_github_repository()
    existing_repository = make_repository()

    github_client.get_repository.return_value = github_repository
    repository_store.get_by_github_id.return_value = existing_repository

    with pytest.raises(
        RepositoryAlreadyExistsError,
        match="Repository already exists",
    ):
        await service.import_repository(
            github_url=GITHUB_URL,
        )

    github_client.get_branch_head.assert_not_awaited()
    repository_store.create.assert_not_awaited()
    repository_version_store.create.assert_not_awaited()
    ingestion_service.create_job.assert_not_awaited()
    ingestion_queue.enqueue.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_repository_rolls_back_on_integrity_error() -> None:
    (
        service,
        session,
        github_client,
        repository_store,
        repository_version_store,
        ingestion_service,
        ingestion_queue,
    ) = make_service()

    github_repository = make_github_repository()
    github_commit = GitHubCommit(
        sha=COMMIT_SHA,
    )

    github_client.get_repository.return_value = github_repository
    github_client.get_branch_head.return_value = github_commit
    repository_store.get_by_github_id.return_value = None
    repository_store.create.side_effect = IntegrityError(
        statement="INSERT",
        params={},
        orig=Exception("duplicate"),
    )

    with pytest.raises(
        RepositoryAlreadyExistsError,
        match="Repository already exists",
    ):
        await service.import_repository(
            github_url=GITHUB_URL,
        )

    session.rollback.assert_awaited_once_with()
    session.commit.assert_not_awaited()
    ingestion_queue.enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_repository_rolls_back_on_db_error() -> None:
    (
        service,
        session,
        github_client,
        repository_store,
        repository_version_store,
        ingestion_service,
        ingestion_queue,
    ) = make_service()

    github_repository = make_github_repository()
    github_commit = GitHubCommit(
        sha=COMMIT_SHA,
    )

    github_client.get_repository.return_value = github_repository
    github_client.get_branch_head.return_value = github_commit
    repository_store.get_by_github_id.return_value = None
    repository_store.create.side_effect = RuntimeError(
        "Database failed",
    )

    with pytest.raises(
        RuntimeError,
        match="Database failed",
    ):
        await service.import_repository(
            github_url=GITHUB_URL,
        )

    session.rollback.assert_awaited_once_with()
    session.commit.assert_not_awaited()
    ingestion_queue.enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_repository_raises_when_dispatch_fails() -> None:
    (
        service,
        session,
        github_client,
        repository_store,
        repository_version_store,
        ingestion_service,
        ingestion_queue,
    ) = make_service()

    github_repository = make_github_repository()
    github_commit = GitHubCommit(
        sha=COMMIT_SHA,
    )
    repository = make_repository()
    repository_version = make_repository_version(repository)
    ingestion_job = make_ingestion_job(repository_version)

    github_client.get_repository.return_value = github_repository
    github_client.get_branch_head.return_value = github_commit
    repository_store.get_by_github_id.return_value = None
    repository_store.create.return_value = repository
    repository_version_store.create.return_value = repository_version
    ingestion_service.create_job.return_value = ingestion_job
    ingestion_queue.enqueue.side_effect = RuntimeError(
        "Redis unavailable",
    )

    with pytest.raises(
        IngestionDispatchError,
        match="Failed to dispatch ingestion job",
    ):
        await service.import_repository(
            github_url=GITHUB_URL,
        )

    session.commit.assert_awaited_once_with()
    session.rollback.assert_awaited_once_with()

    ingestion_queue.enqueue.assert_awaited_once_with(
        ingestion_job_id=ingestion_job.id,
    )

    ingestion_service.mark_queued.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_repository_rolls_back_when_mark_queued_fails() -> None:
    (
        service,
        session,
        github_client,
        repository_store,
        repository_version_store,
        ingestion_service,
        ingestion_queue,
    ) = make_service()

    github_repository = make_github_repository()
    github_commit = GitHubCommit(
        sha=COMMIT_SHA,
    )
    repository = make_repository()
    repository_version = make_repository_version(repository)
    ingestion_job = make_ingestion_job(repository_version)

    github_client.get_repository.return_value = github_repository
    github_client.get_branch_head.return_value = github_commit
    repository_store.get_by_github_id.return_value = None
    repository_store.create.return_value = repository
    repository_version_store.create.return_value = repository_version
    ingestion_service.create_job.return_value = ingestion_job
    ingestion_service.mark_queued.side_effect = RuntimeError(
        "Status update failed",
    )

    with pytest.raises(
        IngestionDispatchError,
        match="Failed to dispatch ingestion job",
    ):
        await service.import_repository(
            github_url=GITHUB_URL,
        )

    assert session.commit.await_count == 1
    session.rollback.assert_awaited_once_with()

    ingestion_queue.enqueue.assert_awaited_once_with(
        ingestion_job_id=ingestion_job.id,
    )

    ingestion_service.mark_queued.assert_awaited_once_with(
        ingestion_job,
    )
