from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import AsyncMock
from uuid import uuid4
from zipfile import ZipFile

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.subsystems import SubsystemEnrichmentBuilder, SubsystemEnrichmentSummary
from src.github.client import GitHubClient
from src.github.schemas import GitHubCommit, GitHubPullRequest, GitHubRepository, GitHubTree
from src.github.store import GitHubArtifactStore
from src.graph.analysis import GraphAnalysisBuilder, GraphAnalysisSummary
from src.graph.filesystem import FilesystemGraphBuilder, FilesystemGraphSummary
from src.graph.history import HistoricalGraphBuilder, HistoricalGraphSummary
from src.graph.javascript import JavaScriptGraphBuilder, JavaScriptGraphSummary
from src.graph.python import PythonGraphBuilder, PythonGraphSummary
from src.ingestion.models import (
    IngestionJob,
    IngestionJobStatus,
    IngestionStage,
    IngestionStageStatus,
)
from src.ingestion.processor import (
    ARCHITECTURE_STAGE_NAME,
    ARTIFACT_DOCUMENTS_STAGE_NAME,
    ARTIFACTS_STAGE_NAME,
    COMMITS_STAGE_NAME,
    DOCUMENTATION_CHUNKS_STAGE_NAME,
    EMBEDDINGS_STAGE_NAME,
    FILESYSTEM_GRAPH_STAGE_NAME,
    GRAPH_ANALYSIS_STAGE_NAME,
    HISTORICAL_GRAPH_STAGE_NAME,
    ISSUES_STAGE_NAME,
    JAVASCRIPT_GRAPH_STAGE_NAME,
    METADATA_STAGE_NAME,
    PULL_REQUESTS_STAGE_NAME,
    PYTHON_GRAPH_STAGE_NAME,
    SOURCE_CONTENTS_STAGE_NAME,
    SOURCE_SUMMARIES_STAGE_NAME,
    SOURCE_TREE_STAGE_NAME,
    SUBSYSTEM_ENRICHMENT_STAGE_NAME,
    SUBSYSTEM_GRAPH_STAGE_NAME,
    SUBSYSTEMS_STAGE_NAME,
    GitHubIngestionLimits,
    GitHubIngestionProcessor,
)
from src.ingestion.service import IngestionService, IngestionStageService
from src.repositories.models import Repository
from src.repositories.service import RepositoryService
from src.repository_versions.models import RepositoryVersion
from src.repository_versions.service import RepositoryVersionService
from src.semantic.architecture import ArchitectureBuilder, ArchitectureBuildSummary
from src.semantic.artifacts import ArtifactDocumentBuilder, ArtifactDocumentSummary
from src.semantic.documentation import DocumentationChunkBuilder, DocumentationChunkSummary
from src.semantic.embeddings import EmbeddingBuilder, EmbeddingBuildSummary
from src.semantic.source_summaries import SourceSummaryBuilder, SourceSummaryBuildSummary
from src.semantic.subsystem_graph import SubsystemGraphBuilder, SubsystemGraphSummary
from src.semantic.subsystems import SubsystemDiscoveryBuilder, SubsystemDiscoverySummary

SNAPSHOT_SHA = "a" * 40
TREE_SHA = "f" * 40


def empty_snapshot_archive() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("acme-trace/", "")
    return buffer.getvalue()


def graph_builder_mocks() -> tuple[
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    filesystem_builder = AsyncMock(spec=FilesystemGraphBuilder)
    filesystem_builder.build.return_value = FilesystemGraphSummary(
        nodes=1,
        edges=0,
        evidence=0,
        directories=0,
        files=0,
    )
    python_builder = AsyncMock(spec=PythonGraphBuilder)
    python_builder.build.return_value = PythonGraphSummary(
        files=0,
        parsed_files=0,
        failed_files=0,
        symbols=0,
        imports=0,
        internal_imports=0,
        external_imports=0,
        unresolved_imports=0,
        failures=(),
    )
    javascript_builder = AsyncMock(spec=JavaScriptGraphBuilder)
    javascript_builder.build.return_value = JavaScriptGraphSummary(
        files=0,
        parsed_files=0,
        failed_files=0,
        symbols=0,
        imports=0,
        exports=0,
        components=0,
        hooks=0,
        internal_imports=0,
        external_imports=0,
        unresolved_imports=0,
        failures=(),
    )
    historical_builder = AsyncMock(spec=HistoricalGraphBuilder)
    historical_builder.build.return_value = HistoricalGraphSummary(
        people=0,
        artifacts=0,
        files=0,
        edges=0,
        evidence=0,
        authored=0,
        reviewed=0,
        modifies=0,
        references=0,
        resolves=0,
        parent_of=0,
        release_includes=0,
        unresolved_files=0,
        unresolved_references=0,
        unresolved_parents=0,
    )
    analysis_builder = AsyncMock(spec=GraphAnalysisBuilder)
    analysis_builder.build.return_value = GraphAnalysisSummary(
        nodes=1,
        edges=0,
        metrics=8,
        connected_components=1,
        communities=0,
        bridges=0,
        dependency_cycles=0,
    )
    documentation_builder = AsyncMock(spec=DocumentationChunkBuilder)
    documentation_builder.build.return_value = DocumentationChunkSummary(
        files=0,
        chunks=0,
        characters=0,
        empty_files=0,
        stale_documents=0,
    )
    artifact_document_builder = AsyncMock(spec=ArtifactDocumentBuilder)
    artifact_document_builder.build.return_value = ArtifactDocumentSummary(
        issues=0,
        pull_requests=0,
        releases=0,
        chunks=0,
        characters=0,
        empty_artifacts=0,
        stale_documents=0,
    )
    source_summary_builder = AsyncMock(spec=SourceSummaryBuilder)
    source_summary_builder.build.return_value = SourceSummaryBuildSummary(
        files=0,
        chunks=0,
        characters=0,
        declarations=0,
        imports=0,
        missing_graph_nodes=0,
        truncated_declarations=0,
        truncated_imports=0,
        stale_documents=0,
    )
    embedding_builder = AsyncMock(spec=EmbeddingBuilder)
    embedding_builder.build.return_value = EmbeddingBuildSummary(
        provider="local",
        model="trace-feature-hashing",
        dimensions=384,
        documents=0,
        batches=0,
    )
    subsystem_builder = AsyncMock(spec=SubsystemDiscoveryBuilder)
    subsystem_builder.build.return_value = SubsystemDiscoverySummary(
        files=0,
        candidates=0,
        memberships=0,
        evidence=0,
        stale_candidates=0,
    )
    subsystem_enrichment_builder = AsyncMock(spec=SubsystemEnrichmentBuilder)
    subsystem_enrichment_builder.build.return_value = SubsystemEnrichmentSummary(
        provider_available=False,
        candidates=0,
        enriched=0,
        confirmed=0,
        retained_as_candidates=0,
        rejected=0,
        model_evidence=0,
    )
    architecture_builder = AsyncMock(spec=ArchitectureBuilder)
    architecture_builder.build.return_value = ArchitectureBuildSummary(
        files=0,
        entry_points=0,
        external_dependencies=0,
        major_external_dependencies=0,
        subsystems=0,
        confirmed_subsystems=0,
        derived_edges=0,
        evidence=0,
        stale_edges=0,
    )
    subsystem_graph_builder = AsyncMock(spec=SubsystemGraphBuilder)
    subsystem_graph_builder.build.return_value = SubsystemGraphSummary(
        subsystems=0,
        file_imports=0,
        dependencies=0,
        evidence=0,
        stale_dependencies=0,
    )
    return (
        filesystem_builder,
        python_builder,
        javascript_builder,
        historical_builder,
        analysis_builder,
        documentation_builder,
        artifact_document_builder,
        source_summary_builder,
        embedding_builder,
        subsystem_builder,
        subsystem_enrichment_builder,
        subsystem_graph_builder,
        architecture_builder,
    )


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
            FILESYSTEM_GRAPH_STAGE_NAME,
            PYTHON_GRAPH_STAGE_NAME,
            JAVASCRIPT_GRAPH_STAGE_NAME,
            HISTORICAL_GRAPH_STAGE_NAME,
            GRAPH_ANALYSIS_STAGE_NAME,
            DOCUMENTATION_CHUNKS_STAGE_NAME,
            ARTIFACT_DOCUMENTS_STAGE_NAME,
            SOURCE_SUMMARIES_STAGE_NAME,
            EMBEDDINGS_STAGE_NAME,
            SUBSYSTEMS_STAGE_NAME,
            SUBSYSTEM_ENRICHMENT_STAGE_NAME,
            SUBSYSTEM_GRAPH_STAGE_NAME,
            ARCHITECTURE_STAGE_NAME,
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
    (
        filesystem_builder,
        python_builder,
        javascript_builder,
        historical_builder,
        analysis_builder,
        documentation_builder,
        artifact_document_builder,
        source_summary_builder,
        embedding_builder,
        subsystem_builder,
        subsystem_enrichment_builder,
        subsystem_graph_builder,
        architecture_builder,
    ) = graph_builder_mocks()

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
        filesystem_graph_builder=filesystem_builder,
        python_graph_builder=python_builder,
        javascript_graph_builder=javascript_builder,
        historical_graph_builder=historical_builder,
        graph_analysis_builder=analysis_builder,
        documentation_chunk_builder=documentation_builder,
        artifact_document_builder=artifact_document_builder,
        source_summary_builder=source_summary_builder,
        embedding_builder=embedding_builder,
        subsystem_discovery_builder=subsystem_builder,
        subsystem_enrichment_builder=subsystem_enrichment_builder,
        subsystem_graph_builder=subsystem_graph_builder,
        architecture_builder=architecture_builder,
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
    assert all(stage.status is IngestionStageStatus.COMPLETED for stage in stages)
    for builder in (
        filesystem_builder,
        python_builder,
        javascript_builder,
        historical_builder,
        analysis_builder,
        documentation_builder,
        artifact_document_builder,
        source_summary_builder,
        embedding_builder,
        subsystem_builder,
        subsystem_enrichment_builder,
        subsystem_graph_builder,
        architecture_builder,
    ):
        builder.build.assert_awaited_once_with(
            repository_id=repository.id,
            repository_version_id=version.id,
        )


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
        FILESYSTEM_GRAPH_STAGE_NAME,
        PYTHON_GRAPH_STAGE_NAME,
        JAVASCRIPT_GRAPH_STAGE_NAME,
        HISTORICAL_GRAPH_STAGE_NAME,
        GRAPH_ANALYSIS_STAGE_NAME,
        DOCUMENTATION_CHUNKS_STAGE_NAME,
        ARTIFACT_DOCUMENTS_STAGE_NAME,
        SOURCE_SUMMARIES_STAGE_NAME,
        EMBEDDINGS_STAGE_NAME,
        SUBSYSTEMS_STAGE_NAME,
        SUBSYSTEM_ENRICHMENT_STAGE_NAME,
        SUBSYSTEM_GRAPH_STAGE_NAME,
        ARCHITECTURE_STAGE_NAME,
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
    (
        filesystem_builder,
        python_builder,
        javascript_builder,
        historical_builder,
        analysis_builder,
        documentation_builder,
        artifact_document_builder,
        source_summary_builder,
        embedding_builder,
        subsystem_builder,
        subsystem_enrichment_builder,
        subsystem_graph_builder,
        architecture_builder,
    ) = graph_builder_mocks()
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
        filesystem_graph_builder=filesystem_builder,
        python_graph_builder=python_builder,
        javascript_graph_builder=javascript_builder,
        historical_graph_builder=historical_builder,
        graph_analysis_builder=analysis_builder,
        documentation_chunk_builder=documentation_builder,
        artifact_document_builder=artifact_document_builder,
        source_summary_builder=source_summary_builder,
        embedding_builder=embedding_builder,
        subsystem_discovery_builder=subsystem_builder,
        subsystem_enrichment_builder=subsystem_enrichment_builder,
        subsystem_graph_builder=subsystem_graph_builder,
        architecture_builder=architecture_builder,
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
    for builder in (
        filesystem_builder,
        python_builder,
        javascript_builder,
        historical_builder,
        analysis_builder,
        documentation_builder,
        artifact_document_builder,
        source_summary_builder,
        embedding_builder,
        subsystem_builder,
        subsystem_enrichment_builder,
        subsystem_graph_builder,
        architecture_builder,
    ):
        builder.build.assert_not_awaited()
