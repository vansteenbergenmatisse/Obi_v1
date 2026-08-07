"""Citation enforcement (ADR-0005 §6): uncited and hallucinated-source claims are stripped."""

from __future__ import annotations

from app.features.rag_agent.domain.citations import enforce_citations


def test_keeps_cited_sentence_and_reports_used_markers() -> None:
    text, used = enforce_citations("The sky is blue [1].", valid_markers={1, 2})
    assert text == "The sky is blue [1]."
    assert used == [1]


def test_strips_uncited_claim() -> None:
    text, used = enforce_citations(
        "Refunds take five days [1]. Everyone knows the moon is cheese.",
        valid_markers={1},
    )
    assert text == "Refunds take five days [1]."
    assert used == [1]


def test_strips_claim_that_only_cites_a_hallucinated_source() -> None:
    # [7] was never retrieved -> the whole claim goes.
    text, used = enforce_citations("Our SLA is 99.99% [7].", valid_markers={1, 2})
    assert text == ""
    assert used == []


def test_drops_invalid_marker_but_keeps_a_validly_cited_sentence() -> None:
    text, used = enforce_citations("Login uses SSO [2][9].", valid_markers={2})
    assert text == "Login uses SSO [2]."
    assert used == [2]


def test_used_markers_are_sorted_and_deduped() -> None:
    _, used = enforce_citations(
        "Alpha [3]. Beta [1][3]. Gamma [1].",
        valid_markers={1, 3},
    )
    assert used == [1, 3]


def test_empty_answer_returns_empty() -> None:
    assert enforce_citations("", valid_markers={1}) == ("", [])
