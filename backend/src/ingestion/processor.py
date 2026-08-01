from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import RetryableGitHubAPIError
from src.github.client import GitHubClient
from src.github.store import GitHubArtifactStore
from src.ingestion.models import (
    IngestionJob,
    IngestionStage,
    IngestionStageStatus,
)
from src.ingestion.runner import MAX_ERROR_MESSAGE_LENGTH
from src.ingestion.service import IngestionService, IngestionStageService
from src.repositories.service import RepositoryService
from src.repository_versions.service import RepositoryVersionService

FOUNDATION_STAGE_NAME = "prepare_repository_snapshot"
METADATA_STAGE_NAME = "fetch_repository_metadata"
SOURCE_TREE_STAGE_NAME = "fetch_source_tree"
ARTIFACTS_STAGE_NAME = "fetch_github_artifacts"


@dataclass(frozen=True, slots=True)
class GitHubIngestionLimits:
    labels: int = 200
    issues: int = 200
    pull_requests: int = 100
    reviews_per_pull_request: int = 100
    changed_files_per_artifact: int = 300
    commits: int = 100
    releases: int = 100
    contributors: int = 100


class FoundationIngestionProcessor:
    def __init__(
        self,
        *,
        session: AsyncSession,
        ingestion_service: IngestionService,
        stage_service: IngestionStageService,
        repository_version_service: RepositoryVersionService,
    ) -> None:
        self.session = session
        self.ingestion_service = ingestion_service
        self.stage_service = stage_service
        self.repository_version_service = repository_version_service

    async def process(self, ingestion_job: IngestionJob) -> None:
        ingestion_stage = await self._get_or_create_stage(ingestion_job)

        if ingestion_stage.status is IngestionStageStatus.COMPLETED:
            await self.ingestion_service.update_progress(
                ingestion_job,
                progress=99,
            )
            await self.session.commit()
            return

        if ingestion_stage.status in {
            IngestionStageStatus.FAILED,
            IngestionStageStatus.SKIPPED,
        }:
            raise RuntimeError(
                f"Foundation stage cannot resume from {ingestion_stage.status.value}",
            )

        try:
            if ingestion_stage.status is IngestionStageStatus.PENDING:
                await self.stage_service.mark_running(ingestion_stage)

            await self.ingestion_service.update_progress(
                ingestion_job,
                progress=10,
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        try:
            await self.repository_version_service.get_repository_version(
                ingestion_job.repository_version_id,
            )
            await self.stage_service.mark_completed(ingestion_stage)
            await self.ingestion_service.update_progress(
                ingestion_job,
                progress=99,
            )
            await self.session.commit()
        except Exception as error:
            await self._record_stage_failure(
                ingestion_stage=ingestion_stage,
                error=error,
            )
            raise

    async def _get_or_create_stage(
        self,
        ingestion_job: IngestionJob,
    ) -> IngestionStage:
        stages = await self.stage_service.list_stages(
            ingestion_job.id,
        )

        for ingestion_stage in stages:
            if ingestion_stage.name == FOUNDATION_STAGE_NAME:
                return ingestion_stage

        return await self.stage_service.create_stage(
            ingestion_job_id=ingestion_job.id,
            name=FOUNDATION_STAGE_NAME,
            position=0,
        )

    async def _record_stage_failure(
        self,
        *,
        ingestion_stage: IngestionStage,
        error: Exception,
    ) -> None:
        ingestion_stage_id = ingestion_stage.id
        await self.session.rollback()

        try:
            persisted_stage = await self.stage_service.get_stage(
                ingestion_stage_id,
            )

            if persisted_stage.status in {
                IngestionStageStatus.PENDING,
                IngestionStageStatus.RUNNING,
            }:
                error_message = str(error) or type(error).__name__
                await self.stage_service.mark_failed(
                    persisted_stage,
                    error_message=error_message[:MAX_ERROR_MESSAGE_LENGTH],
                )
                await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise


class GitHubIngestionProcessor:
    """Persist deterministic GitHub facts for the submission-time snapshot."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        ingestion_service: IngestionService,
        stage_service: IngestionStageService,
        repository_version_service: RepositoryVersionService,
        repository_service: RepositoryService,
        github_client: GitHubClient,
        artifact_store: GitHubArtifactStore,
        limits: GitHubIngestionLimits,
    ) -> None:
        self.session = session
        self.ingestion_service = ingestion_service
        self.stage_service = stage_service
        self.repository_version_service = repository_version_service
        self.repository_service = repository_service
        self.github_client = github_client
        self.artifact_store = artifact_store
        self.limits = limits

    async def process(self, ingestion_job: IngestionJob) -> None:
        stages = await self._ensure_stages(ingestion_job)
        repository_version = await self.repository_version_service.get_repository_version(
            ingestion_job.repository_version_id
        )
        repository = await self.repository_service.get_repository(repository_version.repository_id)

        async def metadata_action() -> dict[str, object]:
            github_repository = await self.github_client.get_repository(
                owner=repository.owner,
                name=repository.name,
            )
            snapshot_commit = await self.github_client.get_commit(
                owner=repository.owner,
                name=repository.name,
                ref=repository_version.commit_sha,
            )
            if snapshot_commit.sha != repository_version.commit_sha:
                raise RuntimeError("GitHub returned a different snapshot SHA")
            if snapshot_commit.commit.tree is None:
                raise RuntimeError("GitHub commit response did not include a source tree SHA")
            languages = await self.github_client.get_languages(
                owner=repository.owner,
                name=repository.name,
            )

            repository.github_url = github_repository.html_url
            repository.owner = github_repository.owner.login
            repository.name = github_repository.name
            repository.default_branch = github_repository.default_branch
            repository.description = github_repository.description
            repository.homepage = github_repository.homepage
            repository.primary_language = github_repository.language
            repository.stars_count = github_repository.stargazers_count
            repository.forks_count = github_repository.forks_count
            repository.watchers_count = github_repository.watchers_count
            repository.open_issues_count = github_repository.open_issues_count
            repository.archived = github_repository.archived
            repository.disabled = github_repository.disabled
            repository.provider_created_at = github_repository.created_at
            repository.provider_updated_at = github_repository.updated_at
            repository.provider_pushed_at = github_repository.pushed_at
            repository_version.languages = languages
            repository_version.source_tree_sha = snapshot_commit.commit.tree.sha
            await self.session.flush()
            return {
                "snapshot_sha": repository_version.commit_sha,
                "source_tree_sha": snapshot_commit.commit.tree.sha,
                "default_branch": github_repository.default_branch,
                "languages": len(languages),
            }

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[METADATA_STAGE_NAME],
            progress=25,
            action=metadata_action,
        )

        async def source_tree_action() -> dict[str, object]:
            if repository_version.source_tree_sha is None:
                raise RuntimeError("Repository snapshot does not have a source tree SHA")
            tree = await self.github_client.get_complete_tree(
                owner=repository.owner,
                name=repository.name,
                tree_sha=repository_version.source_tree_sha,
            )
            if tree.sha != repository_version.source_tree_sha:
                raise RuntimeError("GitHub returned a different source tree SHA")
            repository_version.source_tree_truncated = tree.truncated
            summary = await self.artifact_store.replace_source_tree(
                repository_version_id=repository_version.id,
                tree=tree,
            )
            return {
                "snapshot_sha": repository_version.commit_sha,
                "source_tree_sha": tree.sha,
                **summary,
            }

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[SOURCE_TREE_STAGE_NAME],
            progress=55,
            action=source_tree_action,
        )

        async def artifacts_action() -> dict[str, object]:
            labels = await self.github_client.list_labels(
                owner=repository.owner,
                name=repository.name,
                limit=self.limits.labels,
            )
            issues = await self.github_client.list_issues(
                owner=repository.owner,
                name=repository.name,
                limit=self.limits.issues,
            )
            pull_requests = await self.github_client.list_pull_requests(
                owner=repository.owner,
                name=repository.name,
                limit=self.limits.pull_requests,
            )
            pull_request_files = {}
            pull_request_reviews = {}
            for pull_request in pull_requests:
                pull_request_files[
                    pull_request.number
                ] = await self.github_client.list_pull_request_files(
                    owner=repository.owner,
                    name=repository.name,
                    number=pull_request.number,
                    limit=self.limits.changed_files_per_artifact,
                )
                pull_request_reviews[
                    pull_request.number
                ] = await self.github_client.list_pull_request_reviews(
                    owner=repository.owner,
                    name=repository.name,
                    number=pull_request.number,
                    limit=self.limits.reviews_per_pull_request,
                )

            commit_summaries = await self.github_client.list_commits(
                owner=repository.owner,
                name=repository.name,
                snapshot_sha=repository_version.commit_sha,
                limit=self.limits.commits,
            )
            commits = [
                await self.github_client.get_commit(
                    owner=repository.owner,
                    name=repository.name,
                    ref=commit.sha,
                )
                for commit in commit_summaries
            ]
            releases = await self.github_client.list_releases(
                owner=repository.owner,
                name=repository.name,
                limit=self.limits.releases,
            )
            contributors = await self.github_client.list_contributors(
                owner=repository.owner,
                name=repository.name,
                limit=self.limits.contributors,
            )
            bounds = {
                "snapshot_sha": repository_version.commit_sha,
                "labels": self.limits.labels,
                "issues": self.limits.issues,
                "pull_requests": self.limits.pull_requests,
                "reviews_per_pull_request": self.limits.reviews_per_pull_request,
                "changed_files_per_artifact": self.limits.changed_files_per_artifact,
                "commits": self.limits.commits,
                "releases": self.limits.releases,
                "contributors": self.limits.contributors,
            }
            return await self.artifact_store.persist_artifacts(
                repository_id=repository.id,
                repository_version_id=repository_version.id,
                labels=labels,
                issues=issues,
                pull_requests=pull_requests,
                pull_request_files=pull_request_files,
                pull_request_reviews=pull_request_reviews,
                commits=commits,
                releases=releases,
                contributors=contributors,
                bounds=bounds,
            )

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[ARTIFACTS_STAGE_NAME],
            progress=99,
            action=artifacts_action,
        )

    async def _ensure_stages(self, ingestion_job: IngestionJob) -> dict[str, IngestionStage]:
        existing = {
            stage.name: stage for stage in await self.stage_service.list_stages(ingestion_job.id)
        }
        definitions = (
            (METADATA_STAGE_NAME, 0),
            (SOURCE_TREE_STAGE_NAME, 1),
            (ARTIFACTS_STAGE_NAME, 2),
        )
        for name, position in definitions:
            if name not in existing:
                existing[name] = await self.stage_service.create_stage(
                    ingestion_job_id=ingestion_job.id,
                    name=name,
                    position=position,
                )
        await self.session.commit()
        return existing

    async def _run_stage(
        self,
        *,
        ingestion_job: IngestionJob,
        ingestion_stage: IngestionStage,
        progress: int,
        action: Callable[[], Awaitable[dict[str, object]]],
    ) -> None:
        if ingestion_stage.status is IngestionStageStatus.COMPLETED:
            await self.ingestion_service.update_progress(
                ingestion_job,
                progress=progress,
            )
            await self.session.commit()
            return
        if ingestion_stage.status in {
            IngestionStageStatus.FAILED,
            IngestionStageStatus.SKIPPED,
        }:
            raise RuntimeError(f"Ingestion stage cannot resume from {ingestion_stage.status.value}")

        try:
            if ingestion_stage.status is IngestionStageStatus.PENDING:
                await self.stage_service.mark_running(ingestion_stage)
            await self.session.commit()

            output_summary = await action()
            await self.stage_service.mark_completed(
                ingestion_stage,
                output_summary=output_summary,
            )
            await self.ingestion_service.update_progress(
                ingestion_job,
                progress=progress,
            )
            await self.session.commit()
        except Exception as error:
            if isinstance(error, RetryableGitHubAPIError):
                await self.session.rollback()
                raise
            await self._record_stage_failure(
                ingestion_stage=ingestion_stage,
                error=error,
            )
            raise

    async def _record_stage_failure(
        self,
        *,
        ingestion_stage: IngestionStage,
        error: Exception,
    ) -> None:
        ingestion_stage_id = ingestion_stage.id
        await self.session.rollback()
        persisted_stage = await self.stage_service.get_stage(ingestion_stage_id)
        if persisted_stage.status in {
            IngestionStageStatus.PENDING,
            IngestionStageStatus.RUNNING,
        }:
            error_message = str(error) or type(error).__name__
            await self.stage_service.mark_failed(
                persisted_stage,
                error_message=error_message[:MAX_ERROR_MESSAGE_LENGTH],
            )
            await self.session.commit()
