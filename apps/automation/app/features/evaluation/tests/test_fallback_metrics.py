"""PLAN 9.7: fallback-rate and citation-grounding (faithfulness proxy) metric correctness."""

from __future__ import annotations

import pytest

from app.features.evaluation.metrics.fallback_metrics import (
    citation_grounding_rate,
    fallback_rate,
)


@pytest.mark.parametrize(
    ("outcomes", "expected"),
    [
        ([False, True, True, False], 0.5),
        ([False, False, False], 0.0),
        ([True, True], 1.0),
        ([], 0.0),
    ],
    ids=["mixed_outcomes", "all_grounded", "all_fell_back", "empty_is_zero_not_undefined"],
)
def test_fallback_rate(outcomes: list[bool], expected: float) -> None:
    assert fallback_rate(outcomes) == expected


@pytest.mark.parametrize(
    ("cited_ids", "corpus_ids", "expected"),
    [
        (["1001"], {"1001"}, 1.0),
        (["1001", "9999"], {"1001"}, 0.5),
        ([], {"1001"}, 0.0),
        (["9999"], {"1001"}, 0.0),
    ],
    ids=["fully_grounded", "partial", "no_citations_is_zero", "none_grounded"],
)
def test_citation_grounding_rate(
    cited_ids: list[str], corpus_ids: set[str], expected: float
) -> None:
    assert citation_grounding_rate(cited_ids, corpus_ids) == expected
