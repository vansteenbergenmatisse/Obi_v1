"""Evaluation runner.

``evaluate`` takes a dataset and an injected ranking function and produces an
``EvalReport``. The ranker is injected so the same harness scores a trivial
baseline today and real Phase 3-5 retrieval later without any change here.

The runner is pure with respect to time: the report timestamp is passed in as
``now_iso``. No clock is read inside.
"""

from __future__ import annotations

from collections.abc import Callable

from app.features.evaluation.metrics.retrieval_metrics import (
    hit_rate_at_k,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from app.features.evaluation.schemas import EvalDataset, EvalReport, EvalResult

# A ranker maps (question, scope) -> ranked list of candidate ids.
RankFn = Callable[[str, str | None], list[str]]


def _case_metrics(ranked: list[str], relevant: set[str], k: int) -> dict[str, float]:
    return {
        f"recall@{k}": recall_at_k(ranked, relevant, k),
        f"precision@{k}": precision_at_k(ranked, relevant, k),
        "mrr": mrr(ranked, relevant, k),
        f"ndcg@{k}": ndcg_at_k(ranked, relevant, k),
        f"hit_rate@{k}": hit_rate_at_k(ranked, relevant, k),
    }


def evaluate(
    dataset: EvalDataset,
    rank_fn: RankFn,
    now_iso: str,
    k: int = 5,
) -> EvalReport:
    """Run ``rank_fn`` over every case in ``dataset`` and aggregate metrics.

    Parameters
    ----------
    dataset: the labelled cases to score.
    rank_fn: ``rank_fn(question, scope) -> list[str]`` producing ranked ids.
    now_iso: timestamp string stamped on the report (no hidden clock call).
    k: retrieval cutoff for the @k metrics.
    """
    results: list[EvalResult] = []
    for case in dataset.cases:
        relevant = set(case.relevant_chunk_ids)
        ranked = list(rank_fn(case.question, case.scope))
        metrics = _case_metrics(ranked, relevant, k)
        results.append(
            EvalResult(
                case_id=case.id,
                kind=case.kind,
                ranked_ids=ranked,
                relevant_ids=list(case.relevant_chunk_ids),
                metrics=metrics,
            )
        )

    aggregates = _aggregate(results)
    return EvalReport(
        dataset_name=dataset.name,
        timestamp=now_iso,
        k=k,
        case_count=len(dataset.cases),
        aggregates=aggregates,
        results=results,
    )


def _aggregate(results: list[EvalResult]) -> dict[str, float]:
    """Mean of every metric across cases. Empty dataset yields no aggregates."""
    if not results:
        return {}
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for result in results:
        for name, value in result.metrics.items():
            totals[name] = totals.get(name, 0.0) + value
            counts[name] = counts.get(name, 0) + 1
    return {name: totals[name] / counts[name] for name in totals}


__all__ = ["RankFn", "evaluate"]
