"""`decide_clarification`: heuristic-first, LLM-fallback-only-when-inconclusive — pure logic
against a fake classifier, no network. Also `parse_clarification_reply` (PLAN 9.3): pure parsing
of the clarifying-question generation call's raw text, no network."""

from __future__ import annotations

import pytest

from app.features.rag_agent.domain.clarification import (
    decide_clarification,
    parse_clarification_reply,
)
from app.features.rag_agent.schemas import ChatMessage


class _FakeClassifier:
    def __init__(self, verdict: bool) -> None:
        self._verdict = verdict
        self.called_with: list[str] = []

    def classify(self, query: str) -> bool:
        self.called_with.append(query)
        return self._verdict


class _RaisingClassifier:
    def classify(self, query: str) -> bool:
        raise AssertionError("classifier must not be called when the heuristic is decisive")


def test_long_query_is_never_ambiguous_and_skips_the_classifier() -> None:
    classifier = _RaisingClassifier()
    query = "How do I configure the single sign-on integration for our enterprise Okta tenant?"

    decision = decide_clarification(query, [], classifier)

    assert decision.is_ambiguous is False
    assert "heuristic" in decision.reason


def test_empty_query_is_never_ambiguous_and_skips_the_classifier() -> None:
    decision = decide_clarification("", [], _RaisingClassifier())

    assert decision.is_ambiguous is False
    assert "heuristic" in decision.reason


def test_short_query_falls_through_to_the_classifier_and_returns_its_verdict() -> None:
    classifier = _FakeClassifier(verdict=True)

    decision = decide_clarification("What are the limits?", [], classifier)

    assert decision.is_ambiguous is True
    assert classifier.called_with == ["What are the limits?"]
    assert "classifier" in decision.reason


def test_short_but_specific_query_can_still_be_judged_not_ambiguous() -> None:
    """The heuristic alone cannot distinguish a short vague question from a short specific one —
    both are inconclusive and reach the classifier; only the classifier's verdict decides."""
    classifier = _FakeClassifier(verdict=False)

    decision = decide_clarification("How do I reset my password?", [], classifier)

    assert decision.is_ambiguous is False
    assert classifier.called_with == ["How do I reset my password?"]


def test_r1_clarify_twelve_words_is_the_heuristic_boundary() -> None:
    """panel r1-clarify, check (b): the heuristic boundary is exactly 12 words — 11 or fewer falls
    through to the classifier, 12 or more never does."""
    eleven_words = "how do I configure single sign on for our enterprise Okta"
    assert len(eleven_words.split()) == 11
    classifier = _FakeClassifier(verdict=True)
    decision = decide_clarification(eleven_words, [], classifier)
    assert classifier.called_with == [eleven_words]
    assert decision.is_ambiguous is True

    twelve_words = eleven_words + " tenant"
    assert len(twelve_words.split()) == 12
    decision = decide_clarification(twelve_words, [], _RaisingClassifier())
    assert decision.is_ambiguous is False
    assert "heuristic" in decision.reason


def test_r1_clarify_otherwise_exactly_one_classifier_call() -> None:
    """panel r1-clarify, check (c): when the heuristic is inconclusive, the classifier is called
    exactly once, and its verdict alone decides."""
    classifier = _FakeClassifier(verdict=False)

    decision = decide_clarification("What are the limits?", [], classifier)

    assert classifier.called_with == ["What are the limits?"]
    assert decision.is_ambiguous is False


def test_history_is_accepted_but_not_required_to_be_non_empty() -> None:
    """Signature compatibility (ADR-0008 decision 1) — history isn't consulted yet (see module
    docstring), but passing a real one must not raise or change the outcome."""
    classifier = _FakeClassifier(verdict=True)
    history = [
        ChatMessage(role="user", content="how do I request access?"),
        ChatMessage(role="assistant", content="via the onboarding portal"),
    ]

    decision = decide_clarification("what are the limits?", history, classifier)

    assert decision.is_ambiguous is True


_PARSE_CLARIFICATION_REPLY_CASES = {
    "extracts_question_and_options": (
        "Question: Which limits do you mean?\nOptions:\n- Expense limits\n- Approval thresholds",
        "Which limits do you mean?",
        ["Expense limits", "Approval thresholds"],
    ),
    "accepts_question_only_with_no_options": (
        "Question: What are you asking about?",
        "What are you asking about?",
        [],
    ),
    "is_case_insensitive_on_the_question_prefix": (
        "QUESTION: What do you mean?\nOptions:\n- A\n- B",
        "What do you mean?",
        ["A", "B"],
    ),
    "returns_none_when_no_question_line_is_found": (
        "I'm not sure what you mean.",
        None,
        None,
    ),
    "returns_none_on_empty_text": ("", None, None),
    "ignores_blank_and_stray_lines": (
        "\n\nQuestion: Which system?\n\nOptions:\n\n- Muse\n\n- Toast\n\n",
        "Which system?",
        ["Muse", "Toast"],
    ),
}


@pytest.mark.parametrize(
    ("raw", "expected_question", "expected_options"),
    _PARSE_CLARIFICATION_REPLY_CASES.values(),
    ids=list(_PARSE_CLARIFICATION_REPLY_CASES.keys()),
)
def test_parse_clarification_reply(
    raw: str,
    expected_question: str | None,
    expected_options: list[str] | None,
) -> None:
    reply = parse_clarification_reply(raw)

    if expected_question is None:
        assert reply is None
        return
    assert reply is not None
    assert reply.question == expected_question
    assert reply.options == expected_options
