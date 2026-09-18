"""Citation enforcement (ADR-0005 §6): uncited and hallucinated-source claims are stripped."""

from __future__ import annotations

from app.features.rag_agent.domain.citations import enforce_citations


def test_keeps_cited_sentence_and_reports_used_markers() -> None:
    """panel r5-enforce · substep p0-s0_5-reg-retrieval-stage-5
    Keep a sentence only if it cites at least one valid marker: a sentence citing a
    valid marker survives untouched and the marker is reported as used."""
    text, used = enforce_citations("The sky is blue [1].", valid_markers={1, 2})
    assert text == "The sky is blue [1]."
    assert used == [1]


def test_strips_uncited_claim() -> None:
    """panel r5-enforce · substep p0-s0_5-reg-retrieval-stage-5
    Split into sentences: the answer is split apart so an uncited sentence can be
    dropped while the validly-cited sentence next to it survives."""
    text, used = enforce_citations(
        "Refunds take five days [1]. Everyone knows the moon is cheese.",
        valid_markers={1},
    )
    assert text == "Refunds take five days [1]."
    assert used == [1]


def test_strips_claim_that_only_cites_a_hallucinated_source() -> None:
    """panel r5-enforce · substep p0-s0_5-reg-retrieval-stage-5
    Keep a sentence only if it cites at least one valid marker: a sentence whose only
    marker points at a source that was never retrieved (a hallucinated source) has no
    valid citation left, so it is dropped entirely."""
    # [7] was never retrieved -> the whole claim goes.
    text, used = enforce_citations("Our SLA is 99.99% [7].", valid_markers={1, 2})
    assert text == ""
    assert used == []


def test_drops_invalid_marker_but_keeps_a_validly_cited_sentence() -> None:
    """panel r5-enforce · substep p0-s0_5-reg-retrieval-stage-5
    Strip invented markers from kept sentences: a kept sentence loses its invalid
    marker but keeps its text and its valid marker."""
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
    """panel r5-enforce · substep p0-s0_5-reg-retrieval-stage-5
    Nothing left: when the input itself is empty, enforce_citations has nothing to
    keep and returns empty text and no used markers (the refusal itself -- turning
    "nothing left" into a no_citations refusal -- is panel r5-nocite, in
    answer_service.py, not this pure function)."""
    assert enforce_citations("", valid_markers={1}) == ("", [])


def test_r5_enforce_marker_beyond_evidence_count_is_dropped() -> None:
    """panel r5-enforce · substep p0-s0_5-reg-retrieval-stage-5
    A generator that cites [9] with eight passages: the sentence is dropped. [9] is
    not among the eight valid markers, so the sentence has no valid citation and [9]
    never appears in the used markers."""
    text, used = enforce_citations("Our uptime is 99.9% [9].", valid_markers=set(range(1, 9)))
    assert text == ""
    assert used == []


def test_r5_enforce_keeps_validly_cited_sentence_regardless_of_passage_relevance() -> None:
    """panel r5-enforce · substep p0-s0_5-reg-retrieval-stage-5
    Limit: checks marker validity, not that the passage supports the claim. A sentence
    citing a valid marker is kept even though its content has nothing to do with the
    cited source: enforce_citations only ever sees marker numbers, never passage text,
    so it cannot and does not check groundedness -- that is the separate, batched
    support check that runs next, before anything is sent."""
    text, used = enforce_citations("The moon is made of green cheese [1].", valid_markers={1})
    assert text == "The moon is made of green cheese [1]."
    assert used == [1]
