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
    EvalCase,
    EvalDataset,
    EvalReport,
    EvalResult,
    RerankLiftReport,
    RoutingLiftReport,
)

# A ranker maps (question, scope) -> ranked list of candidate ids.
RankFn = Callable[[str, str | None], list[str]]

# A routing ranker maps a whole case (it needs the case's session_labels) -> ranked candidate ids.
RoutingRankFn = Callable[[EvalCase], list[str]]


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


_ROUTING_METRICS = ("recall", "served_precision", "served_count")


def _routing_metrics(ranked: list[str], relevant: set[str], k: int) -> dict[str, float]:
    """The three routing metrics for one case's served set (substep 9.5.2).

    ``recall`` is set-based (did every relevant page survive the filter) — order-independent, so the
    off/on comparison never depends on the internal tie-break. ``served_precision`` and
    ``served_count`` describe the whole served set: routing narrows it, so precision rises and count
    falls while recall holds.
    """
    served = set(ranked)
    served_count = float(len(served))
    hits = len(served & relevant)
    return {
        "recall": recall_at_k(ranked, relevant, k),
        "served_precision": (hits / served_count) if served_count else 0.0,
        "served_count": served_count,
    }


def evaluate_routing_lift(
    dataset: EvalDataset,
    off_fn: RoutingRankFn,
    on_fn: RoutingRankFn,
    now_iso: str,
    *,
    retrieve_k: int = 50,
) -> RoutingLiftReport:
    """Measure the routing-off vs routing-on lift of the directed-connection hard label filter
    (substep 9.5.2, panel mi-hardfilter) — the rule-11 before/after number that gates 9.4.1.

    ``off_fn`` runs retrieval with NO session labels (the pre-9.4.1 no-op path); ``on_fn`` runs it
    under the case's four directed-connection labels. Both are scored over the same labelled cases
    and the per-metric mean (``after - before``, where before = off, after = on) is returned.
    ``retrieve_k`` is set above the seeded corpus so neither side is truncated before the label
    filter decides the served set. Pure with respect to time — ``now_iso`` is passed in.
    """
    off_tot = dict.fromkeys(_ROUTING_METRICS, 0.0)
    on_tot = dict.fromkeys(_ROUTING_METRICS, 0.0)
    n = 0
    for case in dataset.cases:
        relevant = set(case.relevant_chunk_ids)
        off = _routing_metrics(list(off_fn(case)), relevant, retrieve_k)
        on = _routing_metrics(list(on_fn(case)), relevant, retrieve_k)
        for key in _ROUTING_METRICS:
            off_tot[key] += off[key]
            on_tot[key] += on[key]
        n += 1

    before = {k: (v / n if n else 0.0) for k, v in off_tot.items()}
    after = {k: (v / n if n else 0.0) for k, v in on_tot.items()}
    delta = {k: after[k] - before[k] for k in before}
    return RoutingLiftReport(
        dataset_name=dataset.name,
        timestamp=now_iso,
        case_count=n,
        retrieve_k=retrieve_k,
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


__all__ = [
    "RankFn",
    "RoutingRankFn",
    "evaluate",
    "evaluate_rerank_lift",
    "evaluate_routing_lift",
]
