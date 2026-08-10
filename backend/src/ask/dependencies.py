from typing import Annotated

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.openai_embeddings import OpenAIEmbeddingProvider
from src.ask.answering import ExtractiveAnswerProvider, OpenAIAnswerProvider
from src.ask.retrieval import (
    AdaptiveQueryPlanner,
    HybridRetriever,
    PostgresQueryRetrievalStore,
)
from src.ask.service import RepositoryQueryService
from src.ask.workflow import AskWorkflow
from src.core.config import Settings, get_settings
from src.db.dependencies import get_session
from src.graph.repository import PostgresGraphRepository
from src.repositories.store import RepositoryStore
from src.repository_versions.store import RepositoryVersionStore
from src.semantic.embeddings import LocalHashingEmbeddingProvider
from src.semantic.repository import PostgresSemanticRepository

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_repository_query_service(
    request: Request,
    session: SessionDependency,
    settings: SettingsDependency,
) -> RepositoryQueryService:
    http_client = _openai_http_client(request)
    embedding_provider = (
        OpenAIEmbeddingProvider(
            http_client=http_client,
            api_key=settings.openai_api_key or "",
            model=settings.openai_embedding_model,
            api_url=settings.openai_api_url,
            max_retries=settings.openai_max_retries,
            max_retry_delay_seconds=settings.openai_max_retry_delay_seconds,
        )
        if settings.embedding_provider == "openai"
        else LocalHashingEmbeddingProvider()
    )
    answer_provider = (
        OpenAIAnswerProvider(
            http_client=http_client,
            api_key=settings.openai_api_key or "",
            model=settings.openai_ask_model,
            api_url=settings.openai_api_url,
            max_output_tokens=settings.openai_ask_max_output_tokens,
            max_retries=settings.openai_max_retries,
            max_retry_delay_seconds=settings.openai_max_retry_delay_seconds,
        )
        if settings.openai_ask_enabled
        else ExtractiveAnswerProvider()
    )
    semantic_repository = PostgresSemanticRepository(session=session)
    workflow = AskWorkflow(
        planner=AdaptiveQueryPlanner(),
        retriever=HybridRetriever(
            store=PostgresQueryRetrievalStore(session=session),
            semantic_repository=semantic_repository,
            graph_repository=PostgresGraphRepository(session=session),
            embedding_provider=embedding_provider,
        ),
        answer_provider=answer_provider,
    )
    return RepositoryQueryService(
        repository_store=RepositoryStore(session=session),
        repository_version_store=RepositoryVersionStore(session=session),
        workflow=workflow,
    )


def _openai_http_client(request: Request) -> httpx.AsyncClient:
    client = getattr(request.app.state, "openai_http_client", None)
    if not isinstance(client, httpx.AsyncClient):
        raise RuntimeError("OpenAI HTTP client is not initialized")
    return client
