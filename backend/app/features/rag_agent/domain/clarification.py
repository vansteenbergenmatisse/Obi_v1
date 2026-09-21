"""Ambiguity/vagueness detection (PLAN 9.2, ADR-0008 decision 1) + clarifying-reply parsing
(PLAN 9.3, ADR-0008 decision 3).

Structurally mirrors `domain/small_talk.py`'s shape — a pre-pipeline classifier `AnswerService`
consults before rewrite/retrieval — but cannot be a closed exact-match set: whether a question is
"too vague to search well" depends on open-ended, corpus-specific meaning ("what are the limits?"
is only ambiguous because a real corpus might cover several distinct kinds of limits), not on
matching a known phrase. So this classifier is heuristic-first, LLM-fallback: the heuristic is only
ever confident in one direction — "long enough to have already specified itself, skip the call" —
and every shorter query falls through to a real classifier call rather than being guessed at. This
is the inverse bias of `is_small_talk`'s "never fuzzy, never guess yes": here the heuristic never
guesses yes on ambiguity either, it only ever short-circuits to no.

This module cannot see retrieved evidence (it runs before retrieval), so "ambiguous" here means
"underspecified on its own terms," not "the corpus has multiple matches" — confirming the latter
would require running retrieval first, defeating the point of a pre-retrieval short-circuit.

`decide_clarification` deliberately produces only a yes/no verdict, never clarification text or
options — `parse_clarification_reply` below is the separate, pure piece PLAN 9.3 adds once a verdict
says `is_ambiguous=True`: parsing the actual clarifying question and its 2-4 concrete options out of
`AnthropicAnswerGenerator.generate_clarification`'s raw reply (`infrastructure/llm_client.py`).

`history` is accepted to match the signature ADR-0008 decision 1 locked, but neither the heuristic
nor the classifier call consults it yet — both judge the latest query's text alone. A follow-up
that reads as vague in isolation but is disambiguated by the prior turn (e.g. "what about the
limits?" right after a message that already named a specific system) is not resolved by this phase
— not built here, since nothing in PLAN 9.2's scope needs it yet.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.features.rag_agent.schemas import ChatMessage

# A query with at least this many words has already supplied enough of its own detail to search
# well — if it still comes back empty, that is a corpus-coverage gap (the existing refusal path),
# not a vagueness problem. Below this, the heuristic alone cannot tell a genuinely vague question
# ("what are the limits?") apart from a short-but-specific one ("how do I reset my password?"), so
# both fall through to the classifier rather than being guessed at.
_MIN_WORDS_FOR_HEURISTIC_CONFIDENCE = 12


@dataclass(frozen=True)
class ClarificationDecision:
    """Whether the query is too vague to search well, and why. For logging/tuning only — PLAN 9.3
    generates the user-facing clarifying question and options separately."""

    is_ambiguous: bool
    reason: str


@dataclass(frozen=True)
class ClarificationReply:
    """A clarifying question plus 2-4 concrete options (PLAN 9.3, ADR-0008 decision 3) — the
    user-facing payload `AnswerService` puts on `Answer` once `ClarificationDecision.is_ambiguous`
    is True. ``options`` may be empty (e.g. the fail-open fallback) — the question alone is still
    a valid, if less helpful, clarifying reply."""

    question: str
    options: list[str]


_QUESTION_PREFIX = "question:"
_OPTION_PREFIX = "-"


def parse_clarification_reply(raw: str) -> ClarificationReply | None:
    """Parse the ``CLARIFICATION_SYSTEM_PROMPT``-mandated ``Question: ...\\nOptions:\\n- ...``
    shape. Returns ``None`` on any unparseable reply (no ``Question:`` line found) rather than
    guessing at a partial question — the caller
    (``AnthropicAnswerGenerator.generate_clarification``) fails open to a static fallback on
    ``None``, the same reasoning `AnthropicQueryRewriter.rewrite` applies to a rewrite failure,
    applied here to a malformed generation instead of a transport error.
    """
    question: str | None = None
    options: list[str] = []
    for line in raw.strip().splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(_QUESTION_PREFIX):
            question = stripped[len(_QUESTION_PREFIX) :].strip()
        elif stripped.startswith(_OPTION_PREFIX):
            option = stripped[len(_OPTION_PREFIX) :].strip()
            if option:
                options.append(option)
    if not question:
        return None
    return ClarificationReply(question=question, options=options)


@runtime_checkable
class AmbiguityClassifier(Protocol):
    def classify(self, query: str) -> bool:
        """Return True iff `query`, taken on its own terms, is too vague to search well."""
        ...


def decide_clarification(
    query: str,
    history: Sequence[ChatMessage],
    classifier: AmbiguityClassifier,
) -> ClarificationDecision:
    """Heuristic first, LLM fallback only when inconclusive — never a fuzzy/substring guess."""
    if not query.strip():
        return ClarificationDecision(False, "heuristic: empty query has no ambiguity to clarify")
    if len(query.split()) >= _MIN_WORDS_FOR_HEURISTIC_CONFIDENCE:
        return ClarificationDecision(False, "heuristic: long enough to be self-specifying")
    is_ambiguous = classifier.classify(query)
    reason = (
        "classifier: judged too vague to search well"
        if is_ambiguous
        else "classifier: judged specific enough"
    )
    return ClarificationDecision(is_ambiguous, reason)
