"""Pure retrieval quality metrics.

Every function operates on a ranked list of candidate ids, a set of relevant
ids, and a cutoff ``k``. All functions are pure and free of I/O. Ids are treated
as opaque strings. Duplicate ids in the ranked list are collapsed to their first
occurrence so a candidate cannot be double counted.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def _dedupe_prefix(ranked_ids: Sequence[str], k: int) -> list[str]:
    """Return the first ``k`` distinct ids preserving rank order."""
    if k < 0:
        raise ValueError("k must be non-negative")
    seen: set[str] = set()
    out: list[str] = []
    for item in ranked_ids:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
        if len(out) >= k:
            break
    return out


def recall_at_k(ranked_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> float:
    """Fraction of relevant ids that appear in the top ``k`` results.

    Returns 0.0 when there are no relevant ids (nothing to recall).
    """
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    top = set(_dedupe_prefix(ranked_ids, k))
    hits = len(top & relevant)
    return hits / len(relevant)


def precision_at_k(ranked_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> float:
    """Fraction of the top ``k`` results that are relevant.

    Denominator is ``k`` (the number of positions inspected), not the number of
    results returned, so under-returning is penalised. Returns 0.0 when k == 0.
    """
    if k == 0:
        return 0.0
    relevant = set(relevant_ids)
    top = _dedupe_prefix(ranked_ids, k)
    hits = sum(1 for item in top if item in relevant)
    return hits / k


def mrr(ranked_ids: Sequence[str], relevant_ids: Iterable[str], k: int | None = None) -> float:
    """Reciprocal rank of the first relevant id (1-indexed).

    When ``k`` is given, only the top ``k`` positions are considered. Returns 0.0
    if no relevant id appears in the considered prefix.
    """
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    ordered = _dedupe_prefix(ranked_ids, k) if k is not None else list(dict.fromkeys(ranked_ids))
    for index, item in enumerate(ordered, start=1):
        if item in relevant:
            return 1.0 / index
    return 0.0


def ndcg_at_k(ranked_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> float:
    """Normalised discounted cumulative gain at ``k`` with binary relevance.

    Gain is 1 for a relevant id and 0 otherwise, discounted by log2(rank + 1).
    Normalised against the ideal ordering. Returns 0.0 when there is nothing
    relevant or k == 0.
    """
    if k == 0:
        return 0.0
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    top = _dedupe_prefix(ranked_ids, k)
    dcg = 0.0
    for index, item in enumerate(top, start=1):
        if item in relevant:
            dcg += 1.0 / math.log2(index + 1)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def hit_rate_at_k(ranked_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> float:
    """1.0 if at least one relevant id appears in the top ``k``, else 0.0."""
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    top = set(_dedupe_prefix(ranked_ids, k))
    return 1.0 if top & relevant else 0.0


__all__ = [
    "recall_at_k",
    "precision_at_k",
    "mrr",
    "ndcg_at_k",
    "hit_rate_at_k",
]
