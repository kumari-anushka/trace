from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.openai_embeddings import OpenAIEmbeddingProvider
from src.ask.retrieval import (
    AdaptiveQueryPlanner,
    HybridRetriever,
    PostgresQueryRetrievalStore,
)
from src.core.config import get_settings
from src.db import models as _models  # noqa: F401
from src.db.session import async_session_factory
from src.evaluation.provider import LiveRetrievalRankingProvider, RepositoryScopeResolver
from src.evaluation.retrieval import EvaluationDataset, RetrievalEvaluationHarness
from src.graph.repository import PostgresGraphRepository
from src.repositories.models import Repository
from src.repository_versions.models import RepositoryVersion
from src.semantic.embeddings import LocalHashingEmbeddingProvider
from src.semantic.models import EmbeddingSpace
from src.semantic.repository import PostgresSemanticRepository


class PostgresScopeResolver(RepositoryScopeResolver):
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def resolve(self, repository: str, snapshot_sha: str) -> tuple[UUID, UUID]:
        owner, name = repository.split("/", 1)
        result = await self.session.execute(
            select(Repository.id, RepositoryVersion.id)
            .join(RepositoryVersion, RepositoryVersion.repository_id == Repository.id)
            .where(
                Repository.owner == owner,
                Repository.name == name,
                RepositoryVersion.commit_sha == snapshot_sha,
            )
        )
        row = result.one_or_none()
        if row is None:
            raise ValueError(f"dataset scope {repository}@{snapshot_sha[:8]} is not ingested")
        return row[0], row[1]


class EvaluationRetrievalStore(PostgresQueryRetrievalStore):
    """Select the benchmark provider's space without changing global activation state."""

    def __init__(self, *, session: AsyncSession, provider: str, model: str) -> None:
        super().__init__(session=session)
        self.provider = provider
        self.model = model

    async def active_embedding_space(self) -> EmbeddingSpace | None:
        result = await self.session.execute(
            select(EmbeddingSpace)
            .where(
                EmbeddingSpace.provider == self.provider,
                EmbeddingSpace.model == self.model,
            )
            .order_by(EmbeddingSpace.updated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def run(dataset_path: Path, output_path: Path, *, chart_path: Path | None, k: int) -> None:
    settings = get_settings()
    dataset = EvaluationDataset.load(dataset_path)
    async with (
        async_session_factory() as session,
        httpx.AsyncClient(timeout=httpx.Timeout(settings.openai_timeout_seconds)) as client,
    ):
        embedding_provider = (
            OpenAIEmbeddingProvider(
                http_client=client,
                api_key=settings.openai_api_key or "",
                model=settings.openai_embedding_model,
                api_url=settings.openai_api_url,
                max_retries=settings.openai_max_retries,
                max_retry_delay_seconds=settings.openai_max_retry_delay_seconds,
            )
            if settings.embedding_provider == "openai"
            else LocalHashingEmbeddingProvider()
        )
        retriever = HybridRetriever(
            store=EvaluationRetrievalStore(
                session=session,
                provider=embedding_provider.info.provider,
                model=embedding_provider.info.model,
            ),
            semantic_repository=PostgresSemanticRepository(session=session),
            graph_repository=PostgresGraphRepository(session=session),
            embedding_provider=embedding_provider,
        )
        report = await RetrievalEvaluationHarness(
            provider=LiveRetrievalRankingProvider(
                resolver=PostgresScopeResolver(session=session),
                planner=AdaptiveQueryPlanner(),
                retriever=retriever,
            ),
            k=k,
        ).run(dataset)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report.write(output_path)
    if chart_path is not None:
        chart_path.parent.mkdir(parents=True, exist_ok=True)
        report.write_svg(chart_path)
    for strategy in report.strategies:
        metrics = strategy.metrics
        print(
            f"{strategy.strategy.value:8} "
            f"recall@{k}={metrics.recall_at_k:.3f} "
            f"mrr={metrics.reciprocal_rank:.3f} "
            f"ndcg@{k}={metrics.ndcg_at_k:.3f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Trace retrieval baselines")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=Path("evaluation-report.json"))
    parser.add_argument("--chart", type=Path)
    parser.add_argument("-k", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(run(args.dataset, args.output, chart_path=args.chart, k=args.k))


if __name__ == "__main__":
    main()
