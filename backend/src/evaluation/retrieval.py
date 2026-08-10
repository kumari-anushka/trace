from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RetrievalStrategy(StrEnum):
    KEYWORD = "keyword"
    VECTOR = "vector"
    GRAPH = "graph"
    HYBRID = "hybrid"


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    repository: str = Field(pattern=r"^[^/]+/[^/]+$")
    snapshot_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    question: str = Field(min_length=3)
    category: str = Field(min_length=1)
    difficulty: str = Field(pattern=r"^(easy|medium|hard)$")
    gold_evidence: tuple[str, ...] = Field(min_length=1)

    @field_validator("gold_evidence")
    @classmethod
    def unique_gold_evidence(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("gold_evidence must not contain duplicates")
        return value


class EvaluationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    cases: tuple[EvaluationCase, ...] = Field(min_length=1)

    @field_validator("cases")
    @classmethod
    def unique_case_ids(cls, value: tuple[EvaluationCase, ...]) -> tuple[EvaluationCase, ...]:
        identifiers = [case.id for case in value]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("evaluation case IDs must be unique")
        return value

    @classmethod
    def load(cls, path: Path) -> EvaluationDataset:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


class RankingMetrics(BaseModel):
    precision_at_k: float
    recall_at_k: float
    hit_rate_at_k: float
    reciprocal_rank: float
    ndcg_at_k: float


class CaseEvaluation(BaseModel):
    case_id: str
    strategy: RetrievalStrategy
    retrieved: tuple[str, ...]
    metrics: RankingMetrics


class StrategyEvaluation(BaseModel):
    strategy: RetrievalStrategy
    case_count: int
    metrics: RankingMetrics


class EvaluationReport(BaseModel):
    dataset: str
    dataset_version: str
    k: int
    strategies: tuple[StrategyEvaluation, ...]
    cases: tuple[CaseEvaluation, ...]

    def write(self, path: Path) -> None:
        path.write_text(
            json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def write_svg(self, path: Path) -> None:
        path.write_text(render_evaluation_svg(self), encoding="utf-8")


class RankingProvider(Protocol):
    async def retrieve(
        self, case: EvaluationCase, *, limit: int
    ) -> Mapping[RetrievalStrategy, Sequence[str]]: ...


class RetrievalEvaluationHarness:
    def __init__(self, *, provider: RankingProvider, k: int = 10) -> None:
        if k < 1:
            raise ValueError("k must be positive")
        self.provider = provider
        self.k = k

    async def run(self, dataset: EvaluationDataset) -> EvaluationReport:
        case_results: list[CaseEvaluation] = []
        for case in dataset.cases:
            rankings = await self.provider.retrieve(case, limit=self.k)
            for strategy in RetrievalStrategy:
                retrieved = tuple(rankings.get(strategy, ()))[: self.k]
                case_results.append(
                    CaseEvaluation(
                        case_id=case.id,
                        strategy=strategy,
                        retrieved=retrieved,
                        metrics=evaluate_ranking(retrieved, case.gold_evidence, k=self.k),
                    )
                )
        strategies = tuple(_aggregate(strategy, case_results) for strategy in RetrievalStrategy)
        return EvaluationReport(
            dataset=dataset.name,
            dataset_version=dataset.version,
            k=self.k,
            strategies=strategies,
            cases=tuple(case_results),
        )


def evaluate_ranking(retrieved: Sequence[str], gold: Sequence[str], *, k: int) -> RankingMetrics:
    if k < 1:
        raise ValueError("k must be positive")
    gold_set = set(gold)
    ranked = tuple(retrieved[:k])
    relevant = sum(item in gold_set for item in ranked)
    first_relevant = next(
        (rank for rank, item in enumerate(ranked, start=1) if item in gold_set), None
    )
    dcg = sum(
        1 / math.log2(rank + 1) for rank, item in enumerate(ranked, start=1) if item in gold_set
    )
    ideal_relevant = min(len(gold_set), k)
    ideal_dcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal_relevant + 1))
    return RankingMetrics(
        precision_at_k=relevant / k,
        recall_at_k=relevant / len(gold_set) if gold_set else 0.0,
        hit_rate_at_k=float(relevant > 0),
        reciprocal_rank=1 / first_relevant if first_relevant is not None else 0.0,
        ndcg_at_k=dcg / ideal_dcg if ideal_dcg else 0.0,
    )


def render_evaluation_svg(report: EvaluationReport) -> str:
    plot_left = 72
    plot_top = 76
    plot_height = 238
    plot_width = 650
    ceiling = max(
        0.6,
        max(
            max(item.metrics.recall_at_k, item.metrics.reciprocal_rank)
            for item in report.strategies
        ),
    )
    group_width = plot_width / len(report.strategies)
    bar_width = 34
    bars: list[str] = []
    labels: list[str] = []
    for index, item in enumerate(report.strategies):
        center = plot_left + group_width * (index + 0.5)
        measures = (
            (item.metrics.recall_at_k, "#5de4c7", "Recall@10"),
            (item.metrics.reciprocal_rank, "#7aa2f7", "MRR"),
        )
        for offset, (value, color, label) in enumerate(measures):
            x = center - bar_width - 4 + offset * (bar_width + 8)
            bar_height = value / ceiling * plot_height
            y = plot_top + plot_height - bar_height
            bars.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width}" '
                f'height="{bar_height:.1f}" rx="4" fill="{color}">'
                f"<title>{item.strategy.value} {label}: {value:.3f}</title></rect>"
            )
            labels.append(
                f'<text x="{x + bar_width / 2:.1f}" y="{y - 7:.1f}" '
                f'class="value">{value:.3f}</text>'
            )
        labels.append(
            f'<text x="{center:.1f}" y="342" class="strategy">{item.strategy.value.title()}</text>'
        )
    grid: list[str] = []
    for tick in range(4):
        value = ceiling * tick / 3
        y = plot_top + plot_height - value / ceiling * plot_height
        grid.append(
            f'<line x1="{plot_left}" y1="{y:.1f}" x2="{plot_left + plot_width}" '
            f'y2="{y:.1f}" class="grid"/><text x="60" y="{y + 4:.1f}" '
            f'class="tick">{value:.1f}</text>'
        )
    case_count = len(report.cases) // len(report.strategies)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 390" role="img" '
        'aria-labelledby="title description">\n'
        '<title id="title">Trace retrieval benchmark</title>\n'
        '<desc id="description">Development benchmark comparing Recall at 10 and mean '
        "reciprocal rank for keyword, vector, graph, and hybrid retrieval.</desc>\n"
        "<style>text{font-family:ui-sans-serif,system-ui,sans-serif;fill:#d8dee9}"
        ".title{font-size:20px;font-weight:600}.subtitle,.tick{font-size:11px;fill:#8792a2}"
        ".grid{stroke:#273244;stroke-width:1}.value{font-size:10px;text-anchor:middle}"
        ".strategy{font-size:12px;text-anchor:middle}.legend{font-size:11px}</style>\n"
        '<rect width="760" height="390" rx="16" fill="#0b1018"/>\n'
        '<text x="32" y="36" class="title">Retrieval quality — development benchmark</text>\n'
        f'<text x="32" y="57" class="subtitle">{report.dataset} · '
        f"{case_count} questions · k={report.k}</text>\n"
        + "\n".join(grid)
        + "\n"
        + "\n".join(bars)
        + "\n"
        + "\n".join(labels)
        + '\n<rect x="540" y="30" width="10" height="10" rx="2" fill="#5de4c7"/>'
        '<text x="556" y="39" class="legend">Recall@10</text>'
        '<rect x="635" y="30" width="10" height="10" rx="2" fill="#7aa2f7"/>'
        '<text x="651" y="39" class="legend">MRR</text>\n</svg>\n'
    )


def _aggregate(
    strategy: RetrievalStrategy, case_results: Sequence[CaseEvaluation]
) -> StrategyEvaluation:
    selected = [result.metrics for result in case_results if result.strategy is strategy]
    count = len(selected)
    if count == 0:
        metrics = RankingMetrics(
            precision_at_k=0.0,
            recall_at_k=0.0,
            hit_rate_at_k=0.0,
            reciprocal_rank=0.0,
            ndcg_at_k=0.0,
        )
    else:
        metrics = RankingMetrics(
            precision_at_k=sum(item.precision_at_k for item in selected) / count,
            recall_at_k=sum(item.recall_at_k for item in selected) / count,
            hit_rate_at_k=sum(item.hit_rate_at_k for item in selected) / count,
            reciprocal_rank=sum(item.reciprocal_rank for item in selected) / count,
            ndcg_at_k=sum(item.ndcg_at_k for item in selected) / count,
        )
    return StrategyEvaluation(strategy=strategy, case_count=count, metrics=metrics)
