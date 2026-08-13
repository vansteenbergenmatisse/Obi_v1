"""Refusal-threshold decision (ADR-0005 §7): refuse rather than hallucinate."""

from __future__ import annotations

from app.features.rag_agent.domain.refusal import decide_refusal


def test_refuses_when_top_score_below_threshold() -> None:
    d = decide_refusal(top_score=0.05, threshold=0.10, has_image=False)
    assert d.refuse is True
    assert d.reason == "weak_score"


def test_allows_when_top_score_at_or_above_threshold() -> None:
    assert decide_refusal(top_score=0.10, threshold=0.10, has_image=False).refuse is False
    assert decide_refusal(top_score=0.42, threshold=0.10, has_image=False).refuse is False


def test_allowed_decision_has_no_reason() -> None:
    assert decide_refusal(top_score=0.9, threshold=0.10, has_image=False).reason is None


def test_refuses_when_no_candidates() -> None:
    d = decide_refusal(top_score=None, threshold=0.10, has_image=False)
    assert d.refuse is True
    assert d.reason == "no_candidates"


def test_has_image_never_refuses_on_no_candidates() -> None:
    """ADR-0009 decision 3: a turn whose text retrieval found nothing can still produce a real
    answer from an attached image alone."""
    d = decide_refusal(top_score=None, threshold=0.10, has_image=True)
    assert d.refuse is False
    assert d.reason is None


def test_has_image_never_refuses_on_weak_score() -> None:
    d = decide_refusal(top_score=0.01, threshold=0.10, has_image=True)
    assert d.refuse is False


def test_has_image_true_does_not_change_a_strong_score_outcome() -> None:
    assert decide_refusal(top_score=0.9, threshold=0.10, has_image=True).refuse is False
