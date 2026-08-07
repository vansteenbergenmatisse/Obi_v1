"""Refusal decision (pure, data-driven).

The runtime refuses rather than hallucinate when retrieval is too weak to ground an
answer: either nothing came back, or the top cross-encoder rerank score is below
``refusal_min_rerank_score`` (ADR-0005 §7). The threshold is passed in — this function
reads no settings and no clock, so it is trivially testable and the same rule drives both
the workflow and its eval cases.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RefusalDecision:
    """Whether to refuse, and a human-readable reason (empty when not refusing)."""

    refuse: bool
    reason: str


def decide_refusal(top_score: float | None, threshold: float) -> RefusalDecision:
    """Refuse when there is no candidate, or the best rerank score is below ``threshold``.

    ``top_score`` is the highest cross-encoder score among the reranked, permitted pages
    (``None`` when retrieval returned nothing). Refusal routes the query to a human.
    """
    if top_score is None:
        return RefusalDecision(True, "no retrieved candidates to ground an answer")
    if top_score < threshold:
        return RefusalDecision(
            True,
            f"top relevance {top_score:.3f} below refusal threshold {threshold:.3f}",
        )
    return RefusalDecision(False, "")
