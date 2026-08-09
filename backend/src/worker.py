import asyncio
import logging
import os
import socket

import httpx
from redis.asyncio import Redis

from src.ai.openai import OpenAISubsystemEnrichmentProvider
from src.ai.openai_embeddings import OpenAIEmbeddingProvider
from src.ai.subsystems import PostgresSubsystemEnrichmentReader, SubsystemEnrichmentBuilder
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
from src.semantic.architecture import ArchitectureBuilder, PostgresArchitectureStore
from src.semantic.artifacts import ArtifactDocumentBuilder, PostgresArtifactSourceReader
from src.semantic.documentation import (
    DocumentationChunkBuilder,
    PostgresDocumentationSourceReader,
)
from src.semantic.embeddings import EmbeddingBuilder, LocalHashingEmbeddingProvider
from src.semantic.repository import PostgresSemanticRepository
from src.semantic.source_summaries import PostgresSourceSummaryReader, SourceSummaryBuilder
from src.semantic.subsystem_graph import PostgresSubsystemGraphStore, SubsystemGraphBuilder
from src.semantic.subsystems import PostgresSubsystemDiscoveryStore, SubsystemDiscoveryBuilder


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
            httpx.AsyncClient(
                timeout=httpx.Timeout(settings.openai_timeout_seconds)
            ) as openai_http_client,
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
            subsystem_store = PostgresSubsystemDiscoveryStore(session=session)
            subsystem_enrichment_reader = PostgresSubsystemEnrichmentReader(session=session)
            architecture_store = PostgresArchitectureStore(session=session)
            subsystem_graph_store = PostgresSubsystemGraphStore(session=session)
            subsystem_enrichment_provider = (
                OpenAISubsystemEnrichmentProvider(
                    http_client=openai_http_client,
                    api_key=settings.openai_api_key or "",
                    model=settings.openai_subsystem_model,
                    api_url=settings.openai_api_url,
                    max_output_tokens=settings.openai_max_output_tokens,
                    max_retries=settings.openai_max_retries,
                    max_retry_delay_seconds=settings.openai_max_retry_delay_seconds,
                )
                if settings.openai_subsystem_enrichment_enabled
                else None
            )
            embedding_provider = (
                OpenAIEmbeddingProvider(
                    http_client=openai_http_client,
                    api_key=settings.openai_api_key or "",
                    model=settings.openai_embedding_model,
                    api_url=settings.openai_api_url,
                    max_retries=settings.openai_max_retries,
                    max_retry_delay_seconds=settings.openai_max_retry_delay_seconds,
                )
                if settings.embedding_provider == "openai"
                else LocalHashingEmbeddingProvider()
            )
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
                embedding_builder=EmbeddingBuilder(
                    semantic_repository=semantic_repository,
                    provider=embedding_provider,
                    batch_size=settings.embedding_batch_size,
                ),
                subsystem_discovery_builder=SubsystemDiscoveryBuilder(
                    graph_repository=graph_repository,
                    signal_reader=subsystem_store,
                    candidate_store=subsystem_store,
                ),
                subsystem_enrichment_builder=SubsystemEnrichmentBuilder(
                    graph_repository=graph_repository,
                    reader=subsystem_enrichment_reader,
                    provider=subsystem_enrichment_provider,
                ),
                subsystem_graph_builder=SubsystemGraphBuilder(
                    graph_repository=graph_repository,
                    reader=subsystem_graph_store,
                    store=subsystem_graph_store,
                ),
                architecture_builder=ArchitectureBuilder(
                    graph_repository=graph_repository,
                    reader=architecture_store,
                    store=architecture_store,
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
