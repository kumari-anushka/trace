from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol
from uuid import UUID

from src.ask.models import RetrievalMode
from src.ask.retrieval import (
    AdaptiveQueryPlanner,
    HybridRetriever,
    evidence_evaluation_key,
    reciprocal_rank_fusion,
)
from src.evaluation.retrieval import EvaluationCase, RankingProvider, RetrievalStrategy


class RepositoryScopeResolver(Protocol):
    async def resolve(self, repository: str, snapshot_sha: str) -> tuple[UUID, UUID]: ...


class LiveRetrievalRankingProvider(RankingProvider):
    def __init__(
        self,
        *,
        resolver: RepositoryScopeResolver,
        planner: AdaptiveQueryPlanner,
        retriever: HybridRetriever,
    ) -> None:
        self.resolver = resolver
        self.planner = planner
        self.retriever = retriever

    async def retrieve(
        self, case: EvaluationCase, *, limit: int
    ) -> Mapping[RetrievalStrategy, Sequence[str]]:
        repository_id, version_id = await self.resolver.resolve(case.repository, case.snapshot_sha)
        plan = self.planner.plan(case.question)
        rankings = await self.retriever.retrieve_rankings(
            repository_id=repository_id,
            repository_version_id=version_id,
            question=case.question,
            plan=plan,
            limit=limit,
        )
        hybrid = reciprocal_rank_fusion(rankings, terms=plan.terms, limit=limit)
        by_mode = {
            RetrievalStrategy.KEYWORD: rankings.get(RetrievalMode.METADATA, ()),
            RetrievalStrategy.VECTOR: rankings.get(RetrievalMode.VECTOR, ()),
            RetrievalStrategy.GRAPH: rankings.get(RetrievalMode.GRAPH, ()),
            RetrievalStrategy.HYBRID: hybrid,
        }
        return {
            strategy: tuple(evidence_evaluation_key(item) for item in evidence)
            for strategy, evidence in by_mode.items()
        }
