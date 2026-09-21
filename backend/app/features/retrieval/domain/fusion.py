"""Reciprocal Rank Fusion (pure domain).

Fuses several ranked candidate lists (dense, keyword, ...) into one score per item via
``score = Σ weight / (k0 + rank)`` (rank 1-based). Robust to score-scale differences between
retrievers because it uses ranks, not raw scores.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Hashable, Sequence


def reciprocal_rank_fusion[T: Hashable](
    ranked_lists: Sequence[Sequence[T]],
    *,
    k0: int = 60,
    weights: Sequence[float] | None = None,
) -> dict[T, float]:
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    if len(weights) != len(ranked_lists):
        raise ValueError("weights must match the number of ranked lists")
    scores: dict[T, float] = defaultdict(float)
    for lst, weight in zip(ranked_lists, weights, strict=True):
        for rank, item in enumerate(lst, start=1):
            scores[item] += weight / (k0 + rank)
    return dict(scores)
