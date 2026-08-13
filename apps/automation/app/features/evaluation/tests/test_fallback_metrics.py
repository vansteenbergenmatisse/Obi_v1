"""PLAN 9.7: fallback-rate and citation-grounding (faithfulness proxy) metric correctness."""

from __future__ import annotations

from app.features.evaluation.metrics.fallback_metrics import (
    citation_grounding_rate,
    fallback_rate,
)


def test_fallback_rate_mixed_outcomes() -> None:
    assert fallback_rate([False, True, True, False]) == 0.5


def test_fallback_rate_all_grounded() -> None:
    assert fallback_rate([False, False, False]) == 0.0


def test_fallback_rate_all_fell_back() -> None:
    assert fallback_rate([True, True]) == 1.0


def test_fallback_rate_empty_is_zero_not_undefined() -> None:
    assert fallback_rate([]) == 0.0


def test_citation_grounding_rate_fully_grounded() -> None:
    assert citation_grounding_rate(["1001"], {"1001"}) == 1.0


def test_citation_grounding_rate_partial() -> None:
    assert citation_grounding_rate(["1001", "9999"], {"1001"}) == 0.5


def test_citation_grounding_rate_no_citations_is_zero() -> None:
    assert citation_grounding_rate([], {"1001"}) == 0.0


def test_citation_grounding_rate_none_grounded() -> None:
    assert citation_grounding_rate(["9999"], {"1001"}) == 0.0
