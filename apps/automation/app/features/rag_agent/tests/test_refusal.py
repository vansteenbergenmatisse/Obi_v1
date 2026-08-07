"""Refusal-threshold decision (ADR-0005 §7): refuse rather than hallucinate."""

from __future__ import annotations

from app.features.rag_agent.domain.refusal import decide_refusal


def test_refuses_when_top_score_below_threshold() -> None:
    d = decide_refusal(top_score=0.05, threshold=0.10)
    assert d.refuse is True
    assert "below refusal threshold" in d.reason


def test_allows_when_top_score_at_or_above_threshold() -> None:
    assert decide_refusal(top_score=0.10, threshold=0.10).refuse is False
    assert decide_refusal(top_score=0.42, threshold=0.10).refuse is False


def test_allowed_decision_has_no_reason() -> None:
    assert decide_refusal(top_score=0.9, threshold=0.10).reason == ""


def test_refuses_when_no_candidates() -> None:
    d = decide_refusal(top_score=None, threshold=0.10)
    assert d.refuse is True
    assert "no retrieved candidates" in d.reason
