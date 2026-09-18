"""Refusal-threshold decision (ADR-0005 §7): refuse rather than hallucinate.

2026-09-12: a below-threshold refusal is split by `offtopic_threshold` into `off_topic` (a friendly
redirect, no human hand-off) and `weak_score` (routes to a human). See `domain/refusal.py`.
"""

from __future__ import annotations

from app.features.rag_agent.domain.refusal import decide_refusal
from app.platform.config.settings import Settings

# Measured Cohere rerank-v3.5 top scores on the live test corpus (fork diagnosis 2026-09-12) for
# EQUIVALENT phrasings of a genuinely-SUPPORTED question ("red bananas are the only fruit") vs
# genuinely-UNSUPPORTED / off-topic probes (password / wifi / office hours — nothing in the corpus).
# The distribution is bimodal with an empty gap; the shipped refusal threshold falls in that gap so
# supported phrasings answer, and the off-topic threshold sits just below it so the unsupported
# cluster is recognised as off_topic (redirect), not weak_score (human hand-off).
_SUPPORTED_SCORES = (0.076, 0.089, 0.155)
_UNSUPPORTED_SCORES = (0.019, 0.024, 0.026)

# a convenient default for the fixed-threshold cases below (kept < the 0.10 threshold they use).
_OFFTOPIC = 0.02


def _decide(
    top_score: float | None,
    threshold: float,
    *,
    has_image: bool = False,
    offtopic: float = _OFFTOPIC,
):
    return decide_refusal(top_score, threshold, has_image, offtopic)


def test_shipped_thresholds_map_supported_answer_offtopic_redirect_weak_handoff() -> None:
    refusal = Settings.model_fields["refusal_min_rerank_score"].default
    offtopic = Settings.model_fields["offtopic_max_rerank_score"].default
    assert offtopic < refusal  # the split is only meaningful when this holds
    for score in _SUPPORTED_SCORES:
        assert _decide(score, refusal, offtopic=offtopic).refuse is False, (
            f"supported score {score} wrongly refused at shipped threshold {refusal}"
        )
    for score in _UNSUPPORTED_SCORES:
        d = _decide(score, refusal, offtopic=offtopic)
        assert d.refuse is True and d.reason == "off_topic", (
            f"off-topic score {score} should redirect (off_topic), got {d.reason}"
        )
    # a score between the two thresholds plausibly belongs but can't be grounded -> human hand-off.
    borderline = (offtopic + refusal) / 2
    d = _decide(borderline, refusal, offtopic=offtopic)
    assert d.refuse is True and d.reason == "weak_score"


def test_offtopic_when_candidate_at_or_below_offtopic_threshold() -> None:
    # boundary: `<=` offtopic threshold is off_topic.
    d = _decide(0.02, threshold=0.10, offtopic=0.02)
    assert d.refuse is True
    assert d.reason == "off_topic"


def test_weak_score_when_between_offtopic_and_refusal_threshold() -> None:
    """panel r4-weak · top score below refusal_min_rerank_score refuses with weak_score."""
    d = _decide(0.05, threshold=0.10, offtopic=0.02)
    assert d.refuse is True
    assert d.reason == "weak_score"


def test_no_candidates_is_a_handoff_not_an_offtopic_redirect() -> None:
    # None (retrieval returned nothing) stays no_candidates even though "nothing" scores lowest.
    d = _decide(None, threshold=0.10, offtopic=0.02)
    assert d.refuse is True
    assert d.reason == "no_candidates"


def test_allows_when_top_score_at_or_above_threshold() -> None:
    assert _decide(0.10, threshold=0.10).refuse is False
    assert _decide(0.42, threshold=0.10).refuse is False


def test_allowed_decision_has_no_reason() -> None:
    assert _decide(0.9, threshold=0.10).reason is None


def test_has_image_never_refuses_on_no_candidates() -> None:
    """ADR-0009 decision 3: a turn whose text retrieval found nothing can still produce a real
    answer from an attached image alone."""
    d = _decide(None, threshold=0.10, has_image=True)
    assert d.refuse is False
    assert d.reason is None


def test_has_image_never_refuses_on_offtopic_or_weak_score() -> None:
    assert _decide(0.01, threshold=0.10, has_image=True).refuse is False  # would be off_topic
    assert _decide(0.05, threshold=0.10, has_image=True).refuse is False  # would be weak_score


def test_has_image_true_does_not_change_a_strong_score_outcome() -> None:
    assert _decide(0.9, threshold=0.10, has_image=True).refuse is False
