"""Refusal decision (pure, data-driven).

The runtime refuses rather than hallucinate when retrieval is too weak to ground an
answer: either nothing came back, or the top cross-encoder rerank score is below
``refusal_min_rerank_score`` (ADR-0005 §7). The threshold is passed in — this function
reads no settings and no clock, so it is trivially testable and the same rule drives both
the workflow and its eval cases.

``has_image`` (PLAN 7.3, ADR-0009 decision 3): a turn whose text retrieval found nothing, or
scored below threshold, can still produce a real answer from an attached image alone — refusing
it here would be wrong, not a safe default. This does not touch the separate ``no_citations``
refusal `AnswerService` decides after generation (citation enforcement stripped every claim) —
that one stays unaffected by an image being present, per the ADR.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RefusalDecision:
    """Whether to refuse, and a human-readable reason (empty when not refusing)."""

    refuse: bool
    reason: str


def decide_refusal(top_score: float | None, threshold: float, has_image: bool) -> RefusalDecision:
    """Refuse when there is no candidate, or the best rerank score is below ``threshold`` —
    unless ``has_image`` is true, in which case this never refuses (ADR-0009 decision 3).

    ``top_score`` is the highest cross-encoder score among the reranked, permitted pages
    (``None`` when retrieval returned nothing). Refusal routes the query to a human.

    ``has_image`` has no default: this is a real signature change, not an additive optional
    field — every call site must decide what it means for its turn (ADR-0009 decision 3's own
    "Consequences" note), so a caller cannot silently forget it.
    """
    if has_image:
        return RefusalDecision(False, "")
    if top_score is None:
        return RefusalDecision(True, "no retrieved candidates to ground an answer")
    if top_score < threshold:
        return RefusalDecision(
            True,
            f"top relevance {top_score:.3f} below refusal threshold {threshold:.3f}",
        )
    return RefusalDecision(False, "")
