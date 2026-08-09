from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.subsystems import SubsystemEnrichmentBuilder
from src.core.exceptions import RetryableProviderError
from src.github.classification import extract_text_files_from_zip
from src.github.client import GitHubClient
from src.github.store import GitHubArtifactStore
from src.graph.analysis import GraphAnalysisBuilder
from src.graph.filesystem import FilesystemGraphBuilder
from src.graph.history import HistoricalGraphBuilder
from src.graph.javascript import JavaScriptGraphBuilder
from src.graph.python import PythonGraphBuilder
from src.ingestion.models import IngestionJob, IngestionStage, IngestionStageStatus
from src.ingestion.runner import MAX_ERROR_MESSAGE_LENGTH
from src.ingestion.service import IngestionService, IngestionStageService
from src.repositories.service import RepositoryService
from src.repository_versions.service import RepositoryVersionService
from src.semantic.architecture import ArchitectureBuilder
from src.semantic.artifacts import ArtifactDocumentBuilder
from src.semantic.documentation import DocumentationChunkBuilder
from src.semantic.embeddings import EmbeddingBuilder
from src.semantic.source_summaries import SourceSummaryBuilder
from src.semantic.subsystem_graph import SubsystemGraphBuilder
from src.semantic.subsystems import SubsystemDiscoveryBuilder

FOUNDATION_STAGE_NAME = "prepare_repository_snapshot"
METADATA_STAGE_NAME = "fetch_repository_metadata"
SOURCE_TREE_STAGE_NAME = "fetch_source_tree"
SOURCE_CONTENTS_STAGE_NAME = "fetch_source_contents"
ISSUES_STAGE_NAME = "fetch_issues_and_labels"
PULL_REQUESTS_STAGE_NAME = "fetch_pull_requests"
COMMITS_STAGE_NAME = "fetch_commits"
ARTIFACTS_STAGE_NAME = "fetch_releases_and_contributors"
FILESYSTEM_GRAPH_STAGE_NAME = "build_filesystem_graph"
PYTHON_GRAPH_STAGE_NAME = "build_python_graph"
JAVASCRIPT_GRAPH_STAGE_NAME = "build_javascript_graph"
HISTORICAL_GRAPH_STAGE_NAME = "build_historical_graph"
GRAPH_ANALYSIS_STAGE_NAME = "analyze_repository_graph"
DOCUMENTATION_CHUNKS_STAGE_NAME = "chunk_repository_documentation"
ARTIFACT_DOCUMENTS_STAGE_NAME = "chunk_repository_artifacts"
SOURCE_SUMMARIES_STAGE_NAME = "summarize_source_files"
EMBEDDINGS_STAGE_NAME = "embed_semantic_documents"
SUBSYSTEMS_STAGE_NAME = "discover_subsystem_candidates"
SUBSYSTEM_ENRICHMENT_STAGE_NAME = "enrich_subsystem_candidates"
SUBSYSTEM_GRAPH_STAGE_NAME = "generate_subsystem_graph"
ARCHITECTURE_STAGE_NAME = "generate_architecture_summary"

STAGE_DEFINITIONS = (
    (METADATA_STAGE_NAME, 0, 15),
    (SOURCE_TREE_STAGE_NAME, 1, 30),
    (SOURCE_CONTENTS_STAGE_NAME, 2, 45),
    (ISSUES_STAGE_NAME, 3, 60),
    (PULL_REQUESTS_STAGE_NAME, 4, 78),
    (COMMITS_STAGE_NAME, 5, 92),
    (ARTIFACTS_STAGE_NAME, 6, 93),
    (FILESYSTEM_GRAPH_STAGE_NAME, 7, 95),
    (PYTHON_GRAPH_STAGE_NAME, 8, 97),
    (JAVASCRIPT_GRAPH_STAGE_NAME, 9, 98),
    (HISTORICAL_GRAPH_STAGE_NAME, 10, 99),
    (GRAPH_ANALYSIS_STAGE_NAME, 11, 99),
    (DOCUMENTATION_CHUNKS_STAGE_NAME, 12, 99),
    (ARTIFACT_DOCUMENTS_STAGE_NAME, 13, 99),
    (SOURCE_SUMMARIES_STAGE_NAME, 14, 99),
    (EMBEDDINGS_STAGE_NAME, 15, 99),
    (SUBSYSTEMS_STAGE_NAME, 16, 99),
    (SUBSYSTEM_ENRICHMENT_STAGE_NAME, 17, 99),
    (SUBSYSTEM_GRAPH_STAGE_NAME, 18, 99),
    (ARCHITECTURE_STAGE_NAME, 19, 99),
)


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
    archive_max_bytes: int = 250_000_000
    source_file_max_bytes: int = 1_000_000


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
            await self.ingestion_service.update_progress(ingestion_job, progress=99)
            await self.session.commit()
            return
        if ingestion_stage.status in {
            IngestionStageStatus.FAILED,
            IngestionStageStatus.SKIPPED,
        }:
            raise RuntimeError(
                f"Foundation stage cannot resume from {ingestion_stage.status.value}"
            )

        try:
            if ingestion_stage.status is IngestionStageStatus.PENDING:
                await self.stage_service.mark_running(ingestion_stage)
            await self.ingestion_service.update_progress(ingestion_job, progress=10)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        try:
            await self.repository_version_service.get_repository_version(
                ingestion_job.repository_version_id
            )
            await self.stage_service.mark_completed(ingestion_stage)
            await self.ingestion_service.update_progress(ingestion_job, progress=99)
            await self.session.commit()
        except Exception as error:
            await self._record_stage_failure(ingestion_stage=ingestion_stage, error=error)
            raise

    async def _get_or_create_stage(self, ingestion_job: IngestionJob) -> IngestionStage:
        stages = await self.stage_service.list_stages(ingestion_job.id)
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
        except Exception:
            await self.session.rollback()
            raise


StageAction = Callable[[], Awaitable[dict[str, object]]]


class GitHubIngestionProcessor:
    """Persist deterministic facts with resumable provider checkpoints."""

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
        filesystem_graph_builder: FilesystemGraphBuilder,
        python_graph_builder: PythonGraphBuilder,
        javascript_graph_builder: JavaScriptGraphBuilder,
        historical_graph_builder: HistoricalGraphBuilder,
        graph_analysis_builder: GraphAnalysisBuilder,
        documentation_chunk_builder: DocumentationChunkBuilder,
        artifact_document_builder: ArtifactDocumentBuilder,
        source_summary_builder: SourceSummaryBuilder,
        embedding_builder: EmbeddingBuilder,
        subsystem_discovery_builder: SubsystemDiscoveryBuilder,
        subsystem_enrichment_builder: SubsystemEnrichmentBuilder,
        subsystem_graph_builder: SubsystemGraphBuilder,
        architecture_builder: ArchitectureBuilder,
        limits: GitHubIngestionLimits,
    ) -> None:
        self.session = session
        self.ingestion_service = ingestion_service
        self.stage_service = stage_service
        self.repository_version_service = repository_version_service
        self.repository_service = repository_service
        self.github_client = github_client
        self.artifact_store = artifact_store
        self.filesystem_graph_builder = filesystem_graph_builder
        self.python_graph_builder = python_graph_builder
        self.javascript_graph_builder = javascript_graph_builder
        self.historical_graph_builder = historical_graph_builder
        self.graph_analysis_builder = graph_analysis_builder
        self.documentation_chunk_builder = documentation_chunk_builder
        self.artifact_document_builder = artifact_document_builder
        self.source_summary_builder = source_summary_builder
        self.embedding_builder = embedding_builder
        self.subsystem_discovery_builder = subsystem_discovery_builder
        self.subsystem_enrichment_builder = subsystem_enrichment_builder
        self.subsystem_graph_builder = subsystem_graph_builder
        self.architecture_builder = architecture_builder
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
            completed_progress=15,
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
            completed_progress=30,
            action=source_tree_action,
        )

        async def source_contents_action() -> dict[str, object]:
            candidate_paths = await self.artifact_store.list_content_candidate_paths(
                repository_version_id=repository_version.id
            )
            await self.session.commit()
            archive = await self.github_client.download_snapshot_archive(
                owner=repository.owner,
                name=repository.name,
                commit_sha=repository_version.commit_sha,
                max_bytes=self.limits.archive_max_bytes,
            )
            extraction = extract_text_files_from_zip(
                archive,
                allowed_paths=candidate_paths,
                max_file_bytes=self.limits.source_file_max_bytes,
            )
            summary = await self.artifact_store.replace_source_contents(
                repository_version_id=repository_version.id,
                extraction=extraction,
            )
            return {"archive_bytes": len(archive), **summary}

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[SOURCE_CONTENTS_STAGE_NAME],
            completed_progress=45,
            action=source_contents_action,
        )

        async def issues_action() -> dict[str, object]:
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
            result = await self.artifact_store.persist_labels_and_issues(
                repository_id=repository.id,
                labels=labels,
                issues=issues,
            )
            return cast(dict[str, object], result)

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[ISSUES_STAGE_NAME],
            completed_progress=60,
            action=issues_action,
        )

        pull_request_stage = stages[PULL_REQUESTS_STAGE_NAME]

        async def pull_requests_action() -> dict[str, object]:
            pull_requests = await self.github_client.list_pull_requests(
                owner=repository.owner,
                name=repository.name,
                limit=self.limits.pull_requests,
            )
            checkpoint = pull_request_stage.output_summary or {}
            processed = self._checkpoint_ints(checkpoint, "_processed_numbers")
            file_count = self._summary_int(checkpoint, "pull_request_files")
            review_count = self._summary_int(checkpoint, "reviews")
            for pull_request in pull_requests:
                if pull_request.number in processed:
                    continue
                files = await self.github_client.list_pull_request_files(
                    owner=repository.owner,
                    name=repository.name,
                    number=pull_request.number,
                    limit=self.limits.changed_files_per_artifact,
                )
                reviews = await self.github_client.list_pull_request_reviews(
                    owner=repository.owner,
                    name=repository.name,
                    number=pull_request.number,
                    limit=self.limits.reviews_per_pull_request,
                )
                item_summary = await self.artifact_store.persist_pull_requests(
                    repository_id=repository.id,
                    pull_requests=[pull_request],
                    pull_request_files={pull_request.number: files},
                    pull_request_reviews={pull_request.number: reviews},
                )
                file_count += item_summary["pull_request_files"]
                review_count += item_summary["reviews"]
                processed.add(pull_request.number)
                summary: dict[str, object] = {
                    "pull_requests": len(processed),
                    "pull_request_files": file_count,
                    "reviews": review_count,
                    "_processed_numbers": sorted(processed),
                    "_total": len(pull_requests),
                }
                await self._save_checkpoint(
                    ingestion_job=ingestion_job,
                    ingestion_stage=pull_request_stage,
                    processed=len(processed),
                    total=len(pull_requests),
                    overall_start=60,
                    overall_end=78,
                    output_summary=summary,
                )
            return {
                "pull_requests": len(processed),
                "pull_request_files": file_count,
                "reviews": review_count,
            }

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=pull_request_stage,
            completed_progress=78,
            action=pull_requests_action,
        )

        commit_stage = stages[COMMITS_STAGE_NAME]

        async def commits_action() -> dict[str, object]:
            commit_summaries = await self.github_client.list_commits(
                owner=repository.owner,
                name=repository.name,
                snapshot_sha=repository_version.commit_sha,
                limit=self.limits.commits,
            )
            checkpoint = commit_stage.output_summary or {}
            processed = self._checkpoint_strings(checkpoint, "_processed_shas")
            commit_file_count = self._summary_int(checkpoint, "commit_files")
            for commit_summary in commit_summaries:
                if commit_summary.sha in processed:
                    continue
                commit = await self.github_client.get_commit(
                    owner=repository.owner,
                    name=repository.name,
                    ref=commit_summary.sha,
                )
                item_summary = await self.artifact_store.persist_commits(
                    repository_id=repository.id,
                    commits=[commit],
                )
                commit_file_count += item_summary["commit_files"]
                processed.add(commit.sha)
                summary = {
                    "commits": len(processed),
                    "commit_files": commit_file_count,
                    "_processed_shas": sorted(processed),
                    "_total": len(commit_summaries),
                }
                await self._save_checkpoint(
                    ingestion_job=ingestion_job,
                    ingestion_stage=commit_stage,
                    processed=len(processed),
                    total=len(commit_summaries),
                    overall_start=78,
                    overall_end=92,
                    output_summary=summary,
                )
            return {"commits": len(processed), "commit_files": commit_file_count}

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=commit_stage,
            completed_progress=92,
            action=commits_action,
        )

        async def final_artifacts_action() -> dict[str, object]:
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
            result = await self.artifact_store.persist_releases_and_contributors(
                repository_id=repository.id,
                releases=releases,
                contributors=contributors,
            )
            await self.artifact_store.persist_artifact_snapshot(
                repository_version_id=repository_version.id,
                bounds=self._artifact_bounds(repository_version.commit_sha),
            )
            return cast(dict[str, object], result)

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[ARTIFACTS_STAGE_NAME],
            completed_progress=93,
            action=final_artifacts_action,
        )

        async def filesystem_graph_action() -> dict[str, object]:
            summary = await self.filesystem_graph_builder.build(
                repository_id=repository.id,
                repository_version_id=repository_version.id,
            )
            return cast(dict[str, object], asdict(summary))

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[FILESYSTEM_GRAPH_STAGE_NAME],
            completed_progress=95,
            action=filesystem_graph_action,
        )

        async def python_graph_action() -> dict[str, object]:
            summary = await self.python_graph_builder.build(
                repository_id=repository.id,
                repository_version_id=repository_version.id,
            )
            return cast(dict[str, object], asdict(summary))

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[PYTHON_GRAPH_STAGE_NAME],
            completed_progress=97,
            action=python_graph_action,
        )

        async def javascript_graph_action() -> dict[str, object]:
            summary = await self.javascript_graph_builder.build(
                repository_id=repository.id,
                repository_version_id=repository_version.id,
            )
            return cast(dict[str, object], asdict(summary))

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[JAVASCRIPT_GRAPH_STAGE_NAME],
            completed_progress=98,
            action=javascript_graph_action,
        )

        async def historical_graph_action() -> dict[str, object]:
            summary = await self.historical_graph_builder.build(
                repository_id=repository.id,
                repository_version_id=repository_version.id,
            )
            return cast(dict[str, object], asdict(summary))

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[HISTORICAL_GRAPH_STAGE_NAME],
            completed_progress=99,
            action=historical_graph_action,
        )

        async def graph_analysis_action() -> dict[str, object]:
            summary = await self.graph_analysis_builder.build(
                repository_id=repository.id,
                repository_version_id=repository_version.id,
            )
            return cast(dict[str, object], asdict(summary))

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[GRAPH_ANALYSIS_STAGE_NAME],
            completed_progress=99,
            action=graph_analysis_action,
        )

        async def documentation_chunks_action() -> dict[str, object]:
            summary = await self.documentation_chunk_builder.build(
                repository_id=repository.id,
                repository_version_id=repository_version.id,
            )
            return cast(dict[str, object], asdict(summary))

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[DOCUMENTATION_CHUNKS_STAGE_NAME],
            completed_progress=99,
            action=documentation_chunks_action,
        )

        async def artifact_documents_action() -> dict[str, object]:
            summary = await self.artifact_document_builder.build(
                repository_id=repository.id,
                repository_version_id=repository_version.id,
            )
            return cast(dict[str, object], asdict(summary))

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[ARTIFACT_DOCUMENTS_STAGE_NAME],
            completed_progress=99,
            action=artifact_documents_action,
        )

        async def source_summaries_action() -> dict[str, object]:
            summary = await self.source_summary_builder.build(
                repository_id=repository.id,
                repository_version_id=repository_version.id,
            )
            return cast(dict[str, object], asdict(summary))

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[SOURCE_SUMMARIES_STAGE_NAME],
            completed_progress=99,
            action=source_summaries_action,
        )

        async def embeddings_action() -> dict[str, object]:
            summary = await self.embedding_builder.build(
                repository_id=repository.id,
                repository_version_id=repository_version.id,
            )
            return cast(dict[str, object], asdict(summary))

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[EMBEDDINGS_STAGE_NAME],
            completed_progress=99,
            action=embeddings_action,
        )

        async def subsystems_action() -> dict[str, object]:
            summary = await self.subsystem_discovery_builder.build(
                repository_id=repository.id,
                repository_version_id=repository_version.id,
            )
            return cast(dict[str, object], asdict(summary))

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[SUBSYSTEMS_STAGE_NAME],
            completed_progress=99,
            action=subsystems_action,
        )

        async def subsystem_enrichment_action() -> dict[str, object]:
            summary = await self.subsystem_enrichment_builder.build(
                repository_id=repository.id,
                repository_version_id=repository_version.id,
            )
            return cast(dict[str, object], asdict(summary))

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[SUBSYSTEM_ENRICHMENT_STAGE_NAME],
            completed_progress=99,
            action=subsystem_enrichment_action,
        )

        async def subsystem_graph_action() -> dict[str, object]:
            summary = await self.subsystem_graph_builder.build(
                repository_id=repository.id,
                repository_version_id=repository_version.id,
            )
            return cast(dict[str, object], asdict(summary))

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[SUBSYSTEM_GRAPH_STAGE_NAME],
            completed_progress=99,
            action=subsystem_graph_action,
        )

        async def architecture_action() -> dict[str, object]:
            summary = await self.architecture_builder.build(
                repository_id=repository.id,
                repository_version_id=repository_version.id,
            )
            return cast(dict[str, object], asdict(summary))

        await self._run_stage(
            ingestion_job=ingestion_job,
            ingestion_stage=stages[ARCHITECTURE_STAGE_NAME],
            completed_progress=99,
            action=architecture_action,
        )

    async def _ensure_stages(self, ingestion_job: IngestionJob) -> dict[str, IngestionStage]:
        existing = {
            stage.name: stage for stage in await self.stage_service.list_stages(ingestion_job.id)
        }
        for name, position, _ in STAGE_DEFINITIONS:
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
        completed_progress: int,
        action: StageAction,
    ) -> None:
        if ingestion_stage.status is IngestionStageStatus.COMPLETED:
            await self._advance_job_progress(ingestion_job, completed_progress)
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
            await self._advance_job_progress(ingestion_job, completed_progress)
            await self.session.commit()
        except Exception as error:
            if isinstance(error, RetryableProviderError):
                await self.session.rollback()
                raise
            await self._record_stage_failure(ingestion_stage=ingestion_stage, error=error)
            raise

    async def _save_checkpoint(
        self,
        *,
        ingestion_job: IngestionJob,
        ingestion_stage: IngestionStage,
        processed: int,
        total: int,
        overall_start: int,
        overall_end: int,
        output_summary: dict[str, object],
    ) -> None:
        ratio = 1.0 if total == 0 else processed / total
        stage_progress = min(99, int(ratio * 100))
        overall_progress = min(
            overall_end - 1, overall_start + int(ratio * (overall_end - overall_start))
        )
        await self.stage_service.update_progress(
            ingestion_stage,
            progress=stage_progress,
            output_summary=output_summary,
        )
        await self._advance_job_progress(ingestion_job, overall_progress)
        await self.session.commit()

    async def _advance_job_progress(
        self,
        ingestion_job: IngestionJob,
        progress: int,
    ) -> None:
        if progress > ingestion_job.progress:
            await self.ingestion_service.update_progress(ingestion_job, progress=progress)

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

    def _artifact_bounds(self, snapshot_sha: str) -> dict[str, object]:
        return {
            "snapshot_sha": snapshot_sha,
            "labels": self.limits.labels,
            "issues": self.limits.issues,
            "pull_requests": self.limits.pull_requests,
            "reviews_per_pull_request": self.limits.reviews_per_pull_request,
            "changed_files_per_artifact": self.limits.changed_files_per_artifact,
            "commits": self.limits.commits,
            "releases": self.limits.releases,
            "contributors": self.limits.contributors,
        }

    @staticmethod
    def _summary_int(summary: dict[str, object], key: str) -> int:
        value = summary.get(key, 0)
        return value if isinstance(value, int) else 0

    @staticmethod
    def _checkpoint_ints(summary: dict[str, object], key: str) -> set[int]:
        value = summary.get(key, [])
        if not isinstance(value, list):
            return set()
        return {item for item in value if isinstance(item, int)}

    @staticmethod
    def _checkpoint_strings(summary: dict[str, object], key: str) -> set[str]:
        value = summary.get(key, [])
        if not isinstance(value, list):
            return set()
        return {item for item in value if isinstance(item, str)}
