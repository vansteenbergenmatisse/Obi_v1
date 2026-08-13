"""`decide_clarification`: heuristic-first, LLM-fallback-only-when-inconclusive — pure logic
against a fake classifier, no network. Also `parse_clarification_reply` (PLAN 9.3): pure parsing
of the clarifying-question generation call's raw text, no network."""

from __future__ import annotations

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


def test_parse_clarification_reply_extracts_question_and_options() -> None:
    raw = "Question: Which limits do you mean?\nOptions:\n- Expense limits\n- Approval thresholds"

    reply = parse_clarification_reply(raw)

    assert reply is not None
    assert reply.question == "Which limits do you mean?"
    assert reply.options == ["Expense limits", "Approval thresholds"]


def test_parse_clarification_reply_accepts_question_only_with_no_options() -> None:
    reply = parse_clarification_reply("Question: What are you asking about?")

    assert reply is not None
    assert reply.question == "What are you asking about?"
    assert reply.options == []


def test_parse_clarification_reply_is_case_insensitive_on_the_question_prefix() -> None:
    reply = parse_clarification_reply("QUESTION: What do you mean?\nOptions:\n- A\n- B")

    assert reply is not None
    assert reply.question == "What do you mean?"


def test_parse_clarification_reply_returns_none_when_no_question_line_is_found() -> None:
    assert parse_clarification_reply("I'm not sure what you mean.") is None


def test_parse_clarification_reply_returns_none_on_empty_text() -> None:
    assert parse_clarification_reply("") is None


def test_parse_clarification_reply_ignores_blank_and_stray_lines() -> None:
    raw = "\n\nQuestion: Which system?\n\nOptions:\n\n- Muse\n\n- Toast\n\n"

    reply = parse_clarification_reply(raw)

    assert reply is not None
    assert reply.question == "Which system?"
    assert reply.options == ["Muse", "Toast"]
