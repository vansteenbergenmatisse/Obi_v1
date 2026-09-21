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
from app.features.evaluation.schemas import (
    EvalDataset,
    EvalReport,
    EvalResult,
    RerankLiftReport,
)

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


def evaluate_rerank_lift(
    dataset: EvalDataset,
    before_fn: RankFn,
    after_fn: RankFn,
    now_iso: str,
    *,
    reranker_model: str,
    precision_k: int = 5,
    ndcg_k: int = 10,
) -> RerankLiftReport:
    """Measure the accuracy lift of the cross-encoder rerank (PLAN 3.5.5).

    ``before_fn`` produces the fused, permission-filtered ranking *without* the real
    reranker (the order-preserving ``FakeReranker``); ``after_fn`` applies it. Both are
    scored over the same cases and the per-metric mean delta (``after - before``) is
    returned. Metrics are the two the plan calls out: ``precision@precision_k`` and
    ``ndcg@ndcg_k``. Pure with respect to time — ``now_iso`` is passed in.

    Note ``ndcg_k`` may exceed ``precision_k``: rank both fns deep enough (``k >= ndcg_k``)
    upstream so the ranking is not truncated before the deeper metric sees it.
    """
    p_key = f"precision@{precision_k}"
    n_key = f"ndcg@{ndcg_k}"

    before_tot = {p_key: 0.0, n_key: 0.0}
    after_tot = {p_key: 0.0, n_key: 0.0}
    n = 0
    for case in dataset.cases:
        relevant = set(case.relevant_chunk_ids)
        before_ranked = list(before_fn(case.question, case.scope))
        after_ranked = list(after_fn(case.question, case.scope))
        before_tot[p_key] += precision_at_k(before_ranked, relevant, precision_k)
        before_tot[n_key] += ndcg_at_k(before_ranked, relevant, ndcg_k)
        after_tot[p_key] += precision_at_k(after_ranked, relevant, precision_k)
        after_tot[n_key] += ndcg_at_k(after_ranked, relevant, ndcg_k)
        n += 1

    before = {k: (v / n if n else 0.0) for k, v in before_tot.items()}
    after = {k: (v / n if n else 0.0) for k, v in after_tot.items()}
    delta = {k: after[k] - before[k] for k in before}
    return RerankLiftReport(
        dataset_name=dataset.name,
        timestamp=now_iso,
        case_count=n,
        precision_k=precision_k,
        ndcg_k=ndcg_k,
        reranker_model=reranker_model,
        before=before,
        after=after,
        delta=delta,
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


__all__ = ["RankFn", "evaluate", "evaluate_rerank_lift"]
