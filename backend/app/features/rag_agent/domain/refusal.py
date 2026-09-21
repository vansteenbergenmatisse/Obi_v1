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

``RefusalReason`` (PLAN 9.4, ADR-0008 decision 4; extended 2026-09-12) is the closed taxonomy —
``no_candidates``, ``off_topic`` and ``weak_score`` are decided here; ``no_citations`` is decided by
`AnswerService` after generation (citation enforcement) and reuses this same type rather than
inventing a second one. This is deliberately a stable category, not the old free-text diagnostic
(e.g. the exact score) — a diagnostic with an interpolated number can't be a groupby key for
fallback-rate reporting (PLAN 9.7) and isn't the "static, templated" string `router.py`'s own
audit-log contract already promised. Score-level detail, if needed for debugging, belongs in a
log line at the call site, not in the value that reaches `Answer.refusal_reason`.

``off_topic`` vs ``weak_score`` (the score split, 2026-09-12): both mean "no groundable answer,"
but they differ in *how far* the best candidate scored below the bar, and the UI treats them
differently. A genuinely unrelated question ("how do I reset my password" against a corpus that has
no such page) scores near the floor of the reranker's range; a question that plausibly belongs but
retrieval couldn't confidently ground scores just under the refusal bar. The measured live
distribution is bimodal (unsupported ≈0.02, supported ≥0.076, empty gap), so a candidate at/below
``offtopic_threshold`` is treated as ``off_topic`` (a friendly "ask me about the docs" redirect, no
human hand-off) while one between the two thresholds stays ``weak_score`` (routes to a human). Both
still refuse — neither ever fabricates. ``no_candidates`` (retrieval returned literally nothing) is
kept as a human hand-off, not an off-topic redirect: an empty result on an in-scope search is a real
"we have a gap" signal, not obviously an off-topic question.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RefusalReason = Literal["no_candidates", "off_topic", "weak_score", "no_citations"]


@dataclass(frozen=True)
class RefusalDecision:
    """Whether to refuse, and the taxonomy reason (``None`` when not refusing)."""

    refuse: bool
    reason: RefusalReason | None


def decide_refusal(
    top_score: float | None,
    threshold: float,
    has_image: bool,
    offtopic_threshold: float,
) -> RefusalDecision:
    """Refuse when there is no candidate, or the best rerank score is below ``threshold`` —
    unless ``has_image`` is true, in which case this never refuses (ADR-0009 decision 3).

    ``top_score`` is the highest cross-encoder score among the reranked, permitted pages
    (``None`` when retrieval returned nothing).

    ``offtopic_threshold`` splits the below-``threshold`` refusal (2026-09-12): a candidate scoring
    at/below it is ``off_topic`` (a friendly redirect, no human hand-off); one between the two
    thresholds is ``weak_score`` (routes to a human). Callers pass
    ``settings.offtopic_max_rerank_score`` (kept ``< threshold``). ``no_candidates`` (nothing came
    back) stays a human hand-off, not a redirect.

    Neither ``has_image`` nor ``offtopic_threshold`` has a default: both are real signature changes,
    not additive optional fields — every call site must decide what they mean for its turn, so a
    caller cannot silently forget them.
    """
    if has_image:
        return RefusalDecision(False, None)
    if top_score is None:
        return RefusalDecision(True, "no_candidates")
    if top_score <= offtopic_threshold:
        return RefusalDecision(True, "off_topic")
    if top_score < threshold:
        return RefusalDecision(True, "weak_score")
    return RefusalDecision(False, None)
