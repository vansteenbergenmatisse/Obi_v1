"""Hand-computed assertions for the retrieval metrics."""

from __future__ import annotations

import math

from app.features.evaluation.metrics.retrieval_metrics import (
    hit_rate_at_k,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


def test_recall_at_k_partial() -> None:
    # 2 of 3 relevant found in top 4
    ranked = ["a", "x", "b", "y", "c"]
    relevant = {"a", "b", "z"}
    # top-4 = a, x, b, y -> hits a, b -> 2 / 3
    assert recall_at_k(ranked, relevant, 4) == 2 / 3


def test_recall_at_k_full_and_empty_relevant() -> None:
    assert recall_at_k(["a", "b"], {"a", "b"}, 5) == 1.0
    assert recall_at_k(["a"], set(), 5) == 0.0


def test_precision_at_k_uses_k_denominator() -> None:
    ranked = ["a", "x", "b"]
    relevant = {"a", "b"}
    # top-5 inspected, only 2 relevant found -> 2 / 5
    assert precision_at_k(ranked, relevant, 5) == 2 / 5
    # top-3 -> 2 relevant / 3
    assert precision_at_k(ranked, relevant, 3) == 2 / 3
    assert precision_at_k(ranked, relevant, 0) == 0.0


def test_mrr_first_relevant_rank() -> None:
    # first relevant at position 3 -> 1/3
    assert mrr(["x", "y", "a", "b"], {"a", "b"}, 5) == 1 / 3
    # relevant at position 1 -> 1.0
    assert mrr(["a", "x"], {"a"}, 5) == 1.0
    # none relevant -> 0.0
    assert mrr(["x", "y"], {"a"}, 5) == 0.0
    # k cutoff excludes a late hit
    assert mrr(["x", "y", "a"], {"a"}, 2) == 0.0


def test_ndcg_at_k_known_value() -> None:
    # relevant at ranks 1 and 3; 2 relevant total, k=3
    ranked = ["a", "x", "b"]
    relevant = {"a", "b"}
    dcg = 1.0 / math.log2(2) + 1.0 / math.log2(4)  # ranks 1 and 3
    idcg = 1.0 / math.log2(2) + 1.0 / math.log2(3)  # ideal ranks 1 and 2
    assert math.isclose(ndcg_at_k(ranked, relevant, 3), dcg / idcg)


def test_ndcg_perfect_and_empty() -> None:
    assert ndcg_at_k(["a", "b"], {"a", "b"}, 2) == 1.0
    assert ndcg_at_k(["a"], set(), 3) == 0.0


def test_hit_rate_at_k() -> None:
    assert hit_rate_at_k(["x", "a"], {"a"}, 5) == 1.0
    assert hit_rate_at_k(["x", "y"], {"a"}, 5) == 0.0
    # relevant beyond cutoff -> miss
    assert hit_rate_at_k(["x", "y", "a"], {"a"}, 2) == 0.0


def test_duplicates_collapsed() -> None:
    # duplicate "a" should not count twice or push "b" out of a k=2 window unfairly
    ranked = ["a", "a", "b"]
    relevant = {"a", "b"}
    # distinct top-2 = a, b -> both relevant
    assert recall_at_k(ranked, relevant, 2) == 1.0
