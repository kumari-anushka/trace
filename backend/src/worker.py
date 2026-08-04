import asyncio
import logging
import os
import socket

import httpx
from redis.asyncio import Redis

from src.core.config import get_settings
from src.db import models as _models  # noqa: F401
from src.db.session import async_session_factory, engine
from src.github.client import GitHubClient
from src.github.store import GitHubArtifactStore
from src.graph.analysis import GraphAnalysisBuilder
from src.graph.filesystem import FilesystemGraphBuilder, PostgresSourceFileReader
from src.graph.history import HistoricalGraphBuilder, PostgresHistoricalArtifactReader
from src.graph.javascript import JavaScriptGraphBuilder, PostgresJavaScriptSourceReader
from src.graph.python import PostgresPythonSourceReader, PythonGraphBuilder
from src.graph.repository import PostgresGraphRepository
from src.ingestion.processor import GitHubIngestionLimits, GitHubIngestionProcessor
from src.ingestion.queue import RedisIngestionConsumer
from src.ingestion.runner import IngestionWorker
from src.ingestion.service import IngestionService, IngestionStageService
from src.ingestion.store import IngestionJobStore, IngestionStageStore
from src.repositories.service import RepositoryService
from src.repositories.store import RepositoryStore
from src.repository_versions.service import RepositoryVersionService
from src.repository_versions.store import RepositoryVersionStore
from src.semantic.artifacts import ArtifactDocumentBuilder, PostgresArtifactSourceReader
from src.semantic.documentation import (
    DocumentationChunkBuilder,
    PostgresDocumentationSourceReader,
)
from src.semantic.repository import PostgresSemanticRepository
from src.semantic.source_summaries import PostgresSourceSummaryReader, SourceSummaryBuilder


async def run_worker() -> None:
    settings = get_settings()
    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5.0,
        socket_timeout=10.0,
        health_check_interval=30,
    )
    consumer_name = f"{socket.gethostname()}-{os.getpid()}"

    try:
        async with (
            async_session_factory() as session,
            httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as github_http_client,
        ):
            ingestion_service = IngestionService(
                store=IngestionJobStore(session=session),
            )
            stage_service = IngestionStageService(
                store=IngestionStageStore(session=session),
            )
            repository_version_service = RepositoryVersionService(
                store=RepositoryVersionStore(session=session),
            )
            repository_store = RepositoryStore(session=session)
            graph_repository = PostgresGraphRepository(session=session)
            semantic_repository = PostgresSemanticRepository(session=session)
            processor = GitHubIngestionProcessor(
                session=session,
                ingestion_service=ingestion_service,
                stage_service=stage_service,
                repository_version_service=repository_version_service,
                repository_service=RepositoryService(
                    session=session,
                    store=repository_store,
                ),
                github_client=GitHubClient(
                    http_client=github_http_client,
                    api_url=settings.github_api_url,
                    token=settings.github_token,
                    max_retries=settings.github_max_retries,
                    max_retry_delay_seconds=settings.github_max_retry_delay_seconds,
                ),
                artifact_store=GitHubArtifactStore(session=session),
                filesystem_graph_builder=FilesystemGraphBuilder(
                    graph_repository=graph_repository,
                    source_file_reader=PostgresSourceFileReader(session=session),
                ),
                python_graph_builder=PythonGraphBuilder(
                    graph_repository=graph_repository,
                    source_reader=PostgresPythonSourceReader(session=session),
                ),
                javascript_graph_builder=JavaScriptGraphBuilder(
                    graph_repository=graph_repository,
                    source_reader=PostgresJavaScriptSourceReader(session=session),
                ),
                historical_graph_builder=HistoricalGraphBuilder(
                    graph_repository=graph_repository,
                    artifact_reader=PostgresHistoricalArtifactReader(session=session),
                ),
                graph_analysis_builder=GraphAnalysisBuilder(repository=graph_repository),
                documentation_chunk_builder=DocumentationChunkBuilder(
                    semantic_repository=semantic_repository,
                    source_reader=PostgresDocumentationSourceReader(session=session),
                ),
                artifact_document_builder=ArtifactDocumentBuilder(
                    semantic_repository=semantic_repository,
                    source_reader=PostgresArtifactSourceReader(session=session),
                ),
                source_summary_builder=SourceSummaryBuilder(
                    semantic_repository=semantic_repository,
                    source_reader=PostgresSourceSummaryReader(session=session),
                ),
                limits=GitHubIngestionLimits(
                    labels=settings.github_label_limit,
                    issues=settings.github_issue_limit,
                    pull_requests=settings.github_pull_request_limit,
                    reviews_per_pull_request=(settings.github_review_limit_per_pull_request),
                    changed_files_per_artifact=(settings.github_changed_file_limit_per_artifact),
                    commits=settings.github_commit_limit,
                    releases=settings.github_release_limit,
                    contributors=settings.github_contributor_limit,
                    archive_max_bytes=settings.github_archive_max_bytes,
                    source_file_max_bytes=settings.github_source_file_max_bytes,
                ),
            )
            worker = IngestionWorker(
                session=session,
                consumer=RedisIngestionConsumer(
                    redis_client=redis_client,
                    consumer_name=consumer_name,
                ),
                ingestion_service=ingestion_service,
                processor=processor,
            )

            await worker.run_forever()
    finally:
        await redis_client.aclose()
        await engine.dispose()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
