from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    IngestionJobNotFoundError,
    InvalidIngestionProgressError,
    InvalidIngestionTransitionError,
    RepositorySnapshotNotFoundError,
    SnapshotAlreadyExistsError,
)
from src.models.enums import IngestionJobStatus, SnapshotStatus
from src.models.ingestion_job import IngestionJob
from src.models.repository import Repository
from src.models.repository_snapshot import RepositorySnapshot
from src.stores.ingestion_job_store import IngestionJobStore
from src.stores.repository_snapshot_store import RepositorySnapshotStore

ALLOWED_INGESTION_TRANSITIONS: dict[
    IngestionJobStatus,
    set[IngestionJobStatus],
] = {
    IngestionJobStatus.PENDING: {
        IngestionJobStatus.QUEUED,
        IngestionJobStatus.RUNNING,
        IngestionJobStatus.FAILED,
    },
    IngestionJobStatus.QUEUED: {
        IngestionJobStatus.RUNNING,
        IngestionJobStatus.FAILED,
    },
    IngestionJobStatus.RUNNING: {
        IngestionJobStatus.RUNNING,
        IngestionJobStatus.COMPLETED,
        IngestionJobStatus.FAILED,
    },
    IngestionJobStatus.COMPLETED: set(),
    IngestionJobStatus.FAILED: set(),
}

SNAPSHOT_STATUS_BY_JOB_STATUS: dict[
    IngestionJobStatus,
    SnapshotStatus,
] = {
    IngestionJobStatus.PENDING: SnapshotStatus.PENDING,
    IngestionJobStatus.QUEUED: SnapshotStatus.PENDING,
    IngestionJobStatus.RUNNING: SnapshotStatus.PENDING,
    IngestionJobStatus.COMPLETED: SnapshotStatus.READY,
    IngestionJobStatus.FAILED: SnapshotStatus.FAILED,
}


class IngestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ingestion_job_store = IngestionJobStore(session)
        self.repository_snapshot_store = RepositorySnapshotStore(session)

    async def create_ingestion(
        self,
        repository: Repository,
        *,
        commit_sha: str,
        default_branch: str,
    ) -> tuple[RepositorySnapshot, IngestionJob]:
        try:
            snapshot = RepositorySnapshot(
                repository_id=repository.id,
                commit_sha=commit_sha,
                default_branch=default_branch,
                status=SnapshotStatus.PENDING,
            )

            self.session.add(snapshot)
            await self.session.flush()

            job = IngestionJob(
                repository_id=repository.id,
                snapshot_id=snapshot.id,
                status=IngestionJobStatus.PENDING,
                progress=0,
            )

            self.session.add(job)
            await self.session.commit()

            await self.session.refresh(snapshot)
            await self.session.refresh(job)

            return snapshot, job

        except IntegrityError as error:
            await self.session.rollback()
            raise SnapshotAlreadyExistsError from error

        except Exception:
            await self.session.rollback()
            raise

    async def get_ingestion_job(
        self,
        *,
        repository_id: int,
        job_id: int,
    ) -> IngestionJob:
        job = await self.ingestion_job_store.get_by_id(job_id)

        if job is None or job.repository_id != repository_id:
            raise IngestionJobNotFoundError

        return job

    async def update_ingestion_job(
        self,
        *,
        job_id: int,
        status: IngestionJobStatus,
        progress: int,
        error_message: str | None = None,
    ) -> IngestionJob:
        job = await self.ingestion_job_store.get_by_id(job_id)

        if job is None:
            raise IngestionJobNotFoundError

        allowed_statuses = ALLOWED_INGESTION_TRANSITIONS[job.status]

        if status not in allowed_statuses:
            raise InvalidIngestionTransitionError(
                f"Cannot transition ingestion job from {job.status} to {status}"
            )

        if progress < job.progress:
            raise InvalidIngestionProgressError("Ingestion progress cannot decrease")

        if status == IngestionJobStatus.COMPLETED and progress != 100:
            raise InvalidIngestionProgressError("Completed ingestion job must have progress 100")

        if status == IngestionJobStatus.FAILED and error_message is None:
            raise InvalidIngestionProgressError(
                "Failed ingestion job must include an error message"
            )

        snapshot = await self.repository_snapshot_store.get_by_id(job.snapshot_id)

        if snapshot is None:
            raise RepositorySnapshotNotFoundError

        job.status = status
        job.progress = progress
        job.error_message = error_message
        snapshot.status = SNAPSHOT_STATUS_BY_JOB_STATUS[status]

        if status == IngestionJobStatus.RUNNING and job.started_at is None:
            job.started_at = datetime.now(UTC)

        if status in {
            IngestionJobStatus.COMPLETED,
            IngestionJobStatus.FAILED,
        }:
            job.completed_at = datetime.now(UTC)

        try:
            await self.session.commit()
            await self.session.refresh(job)
        except Exception:
            await self.session.rollback()
            raise

        return job
