from pathlib import Path

import pytest
from pydantic import ValidationError

from src.evaluation.retrieval import (
    EvaluationCase,
    EvaluationDataset,
    RetrievalEvaluationHarness,
    RetrievalStrategy,
    evaluate_ranking,
    render_evaluation_svg,
)


def evaluation_case(identifier: str = "case-1") -> EvaluationCase:
    return EvaluationCase(
        id=identifier,
        repository="owner/repository",
        snapshot_sha="a" * 40,
        question="Where is ingestion implemented?",
        category="file",
        difficulty="easy",
        gold_evidence=("doc:ingestion", "node:ingestion"),
    )


def test_ranking_metrics_are_computed_at_k() -> None:
    metrics = evaluate_ranking(
        ("miss", "doc:ingestion", "node:ingestion"),
        ("doc:ingestion", "node:ingestion"),
        k=3,
    )

    assert metrics.precision_at_k == pytest.approx(2 / 3)
    assert metrics.recall_at_k == 1.0
    assert metrics.hit_rate_at_k == 1.0
    assert metrics.reciprocal_rank == 0.5
    assert metrics.ndcg_at_k == pytest.approx(0.693426, rel=1e-5)


def test_dataset_rejects_duplicate_case_ids() -> None:
    with pytest.raises(ValidationError, match="case IDs must be unique"):
        EvaluationDataset(name="dataset", version="1", cases=(evaluation_case(), evaluation_case()))


def test_development_dataset_is_valid() -> None:
    root = Path(__file__).parents[3]
    dataset = EvaluationDataset.load(root / "evaluation/datasets/trace-dev-v1.json")

    assert dataset.version == "1.0.0"
    assert len(dataset.cases) == 8


class StaticProvider:
    async def retrieve(
        self, case: EvaluationCase, *, limit: int
    ) -> dict[RetrievalStrategy, tuple[str, ...]]:
        del case, limit
        return {
            RetrievalStrategy.KEYWORD: ("doc:ingestion",),
            RetrievalStrategy.VECTOR: ("miss",),
            RetrievalStrategy.GRAPH: ("node:ingestion",),
            RetrievalStrategy.HYBRID: ("doc:ingestion", "node:ingestion"),
        }


async def test_harness_aggregates_each_baseline() -> None:
    dataset = EvaluationDataset(name="dataset", version="1", cases=(evaluation_case(),))

    report = await RetrievalEvaluationHarness(provider=StaticProvider(), k=2).run(dataset)

    by_strategy = {item.strategy: item for item in report.strategies}
    assert by_strategy[RetrievalStrategy.KEYWORD].metrics.recall_at_k == 0.5
    assert by_strategy[RetrievalStrategy.VECTOR].metrics.hit_rate_at_k == 0.0
    assert by_strategy[RetrievalStrategy.GRAPH].metrics.recall_at_k == 0.5
    assert by_strategy[RetrievalStrategy.HYBRID].metrics.recall_at_k == 1.0

    svg = render_evaluation_svg(report)
    assert "Trace retrieval benchmark" in svg
    assert "Hybrid" in svg
    assert "0.500" in svg
