from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import IngestionJobNotFoundError, RepositoryNotFoundError
from src.ingestion.models import (
    IngestionJob,
    IngestionJobStatus,
    IngestionStage,
    IngestionStageStatus,
)
from src.ingestion.store import IngestionJobStore, IngestionStageStore
from src.repositories.models import Repository
from src.repositories.service import RepositoryIngestionService, RepositoryService
from src.repositories.store import RepositoryStore


def make_repository(
    *,
    repository_id: UUID | None = None,
) -> Repository:
    now = datetime.now(UTC)

    repository = Repository(
        github_id=123456789,
        github_url="https://github.com/kumari-anushka/trace",
        owner="kumari-anushka",
        name="trace",
        default_branch="main",
    )

    repository.id = repository_id or uuid4()
    repository.created_at = now
    repository.updated_at = now

    return repository


def make_service() -> tuple[
    RepositoryService,
    AsyncMock,
    AsyncMock,
]:
    session = AsyncMock(spec=AsyncSession)
    store = AsyncMock(spec=RepositoryStore)

    service = RepositoryService(
        session=session,
        store=store,
    )

    return service, session, store


@pytest.mark.asyncio
async def test_get_repository_returns_repository() -> None:
    service, _, store = make_service()
    repository = make_repository()

    store.get_by_id.return_value = repository

    result = await service.get_repository(repository.id)

    assert result is repository
    store.get_by_id.assert_awaited_once_with(repository.id)


@pytest.mark.asyncio
async def test_get_repository_raises_when_not_found() -> None:
    service, _, store = make_service()
    repository_id = uuid4()

    store.get_by_id.return_value = None

    with pytest.raises(
        RepositoryNotFoundError,
        match="Repository not found",
    ):
        await service.get_repository(repository_id)

    store.get_by_id.assert_awaited_once_with(repository_id)


@pytest.mark.asyncio
async def test_list_repositories_returns_repositories() -> None:
    service, _, store = make_service()

    repositories = [
        make_repository(),
        make_repository(),
    ]

    store.list_all.return_value = repositories

    result = await service.list_repositories()

    assert result == repositories
    store.list_all.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_list_repositories_returns_empty_sequence() -> None:
    service, _, store = make_service()

    store.list_all.return_value = []

    result = await service.list_repositories()

    assert result == []
    store.list_all.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_delete_repository_deletes_and_commits() -> None:
    service, session, store = make_service()
    repository = make_repository()

    store.get_by_id.return_value = repository

    await service.delete_repository(repository.id)

    store.get_by_id.assert_awaited_once_with(repository.id)
    store.delete.assert_awaited_once_with(repository)
    session.commit.assert_awaited_once_with()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_repository_raises_when_not_found() -> None:
    service, session, store = make_service()
    repository_id = uuid4()

    store.get_by_id.return_value = None

    with pytest.raises(
        RepositoryNotFoundError,
        match="Repository not found",
    ):
        await service.delete_repository(repository_id)

    store.get_by_id.assert_awaited_once_with(repository_id)
    store.delete.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_repository_rolls_back_when_delete_fails() -> None:
    service, session, store = make_service()
    repository = make_repository()
    error = RuntimeError("Delete failed")

    store.get_by_id.return_value = repository
    store.delete.side_effect = error

    with pytest.raises(
        RuntimeError,
        match="Delete failed",
    ):
        await service.delete_repository(repository.id)

    store.delete.assert_awaited_once_with(repository)
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_delete_repository_rolls_back_when_commit_fails() -> None:
    service, session, store = make_service()
    repository = make_repository()
    error = RuntimeError("Commit failed")

    store.get_by_id.return_value = repository
    session.commit.side_effect = error

    with pytest.raises(
        RuntimeError,
        match="Commit failed",
    ):
        await service.delete_repository(repository.id)

    store.delete.assert_awaited_once_with(repository)
    session.commit.assert_awaited_once_with()
    session.rollback.assert_awaited_once_with()


def make_ingestion_status_service() -> tuple[
    RepositoryIngestionService,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    repository_store = AsyncMock(spec=RepositoryStore)
    ingestion_job_store = AsyncMock(spec=IngestionJobStore)
    ingestion_stage_store = AsyncMock(spec=IngestionStageStore)

    service = RepositoryIngestionService(
        repository_store=repository_store,
        ingestion_job_store=ingestion_job_store,
        ingestion_stage_store=ingestion_stage_store,
    )

    return (
        service,
        repository_store,
        ingestion_job_store,
        ingestion_stage_store,
    )


@pytest.mark.asyncio
async def test_get_ingestion_status_returns_latest_job_and_stages() -> None:
    (
        service,
        repository_store,
        ingestion_job_store,
        ingestion_stage_store,
    ) = make_ingestion_status_service()
    repository = make_repository()
    ingestion_job = IngestionJob(
        repository_version_id=uuid4(),
        status=IngestionJobStatus.RUNNING,
        progress=40,
    )
    ingestion_job.id = uuid4()
    ingestion_stage = IngestionStage(
        ingestion_job_id=ingestion_job.id,
        name="prepare_repository_snapshot",
        position=0,
        status=IngestionStageStatus.RUNNING,
        progress=40,
    )

    repository_store.get_by_id.return_value = repository
    ingestion_job_store.get_latest_by_repository.return_value = ingestion_job
    ingestion_stage_store.list_by_ingestion_job.return_value = [
        ingestion_stage,
    ]

    result = await service.get_status(repository.id)

    assert result.repository_id == repository.id
    assert result.ingestion_job is ingestion_job
    assert result.stages == [ingestion_stage]
    repository_store.get_by_id.assert_awaited_once_with(repository.id)
    ingestion_job_store.get_latest_by_repository.assert_awaited_once_with(
        repository.id,
    )
    ingestion_stage_store.list_by_ingestion_job.assert_awaited_once_with(
        ingestion_job.id,
    )


@pytest.mark.asyncio
async def test_get_ingestion_status_raises_when_repository_is_missing() -> None:
    (
        service,
        repository_store,
        ingestion_job_store,
        ingestion_stage_store,
    ) = make_ingestion_status_service()
    repository_id = uuid4()
    repository_store.get_by_id.return_value = None

    with pytest.raises(
        RepositoryNotFoundError,
        match="Repository not found",
    ):
        await service.get_status(repository_id)

    ingestion_job_store.get_latest_by_repository.assert_not_awaited()
    ingestion_stage_store.list_by_ingestion_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_ingestion_status_raises_when_job_is_missing() -> None:
    (
        service,
        repository_store,
        ingestion_job_store,
        ingestion_stage_store,
    ) = make_ingestion_status_service()
    repository = make_repository()
    repository_store.get_by_id.return_value = repository
    ingestion_job_store.get_latest_by_repository.return_value = None

    with pytest.raises(
        IngestionJobNotFoundError,
        match="Ingestion job not found",
    ):
        await service.get_status(repository.id)

    ingestion_stage_store.list_by_ingestion_job.assert_not_awaited()
