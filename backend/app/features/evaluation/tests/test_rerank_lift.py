"""Unit tests for the rerank-lift measurement (PLAN 3.5.5).

Pure and deterministic: hand-crafted before/after rankers stand in for the retriever with and
without the cross-encoder, so the metric math is verified without a DB or a hosted key.
"""

from __future__ import annotations

from app.features.evaluation.runner import evaluate_rerank_lift
from app.features.evaluation.schemas import EvalCase, EvalDataset, RerankLiftReport

# Two relevant pages buried at ranks 5-6 pre-rerank; the reranker floats them to the top.
_RELEVANT = ["A", "B"]
_BEFORE = ["X", "Y", "Z", "W", "A", "B", "P", "Q", "R", "S"]
_AFTER = ["A", "B", "X", "Y", "Z", "W", "P", "Q", "R", "S"]


def _dataset() -> EvalDataset:
    return EvalDataset(
        name="lift_fixture",
        cases=[
            EvalCase(id="c1", question="q1", relevant_chunk_ids=_RELEVANT),
            EvalCase(id="c2", question="q2", relevant_chunk_ids=_RELEVANT),
        ],
    )


def test_positive_lift_on_precision_and_ndcg() -> None:
    report = evaluate_rerank_lift(
        _dataset(),
        before_fn=lambda q, s: _BEFORE,
        after_fn=lambda q, s: _AFTER,
        now_iso="unit",
        reranker_model="test",
    )
    assert isinstance(report, RerankLiftReport)
    assert report.case_count == 2
    assert report.precision_k == 5 and report.ndcg_k == 10

    # precision@5: before has 1 of {A,B} in the top 5 (0.2); after has both (0.4).
    assert report.before["precision@5"] == 0.2
    assert report.after["precision@5"] == 0.4
    assert report.delta["precision@5"] == 0.2

    # ndcg@10 strictly improves when relevant pages move up, and both are perfect after.
    assert report.after["ndcg@10"] == 1.0
    assert report.before["ndcg@10"] < report.after["ndcg@10"]
    assert report.delta["ndcg@10"] > 0.0


def test_zero_lift_when_order_unchanged() -> None:
    # FakeReranker is order-preserving, so before == after -> no lift (the CI invariant).
    report = evaluate_rerank_lift(
        _dataset(),
        before_fn=lambda q, s: _BEFORE,
        after_fn=lambda q, s: _BEFORE,
        now_iso="unit",
        reranker_model="fake",
    )
    assert report.delta["precision@5"] == 0.0
    assert report.delta["ndcg@10"] == 0.0
    assert report.before == report.after


def test_empty_dataset_is_safe() -> None:
    report = evaluate_rerank_lift(
        EvalDataset(name="empty", cases=[]),
        before_fn=lambda q, s: _BEFORE,
        after_fn=lambda q, s: _AFTER,
        now_iso="unit",
        reranker_model="test",
    )
    assert report.case_count == 0
    assert report.before == {"precision@5": 0.0, "ndcg@10": 0.0}
    assert report.delta == {"precision@5": 0.0, "ndcg@10": 0.0}
