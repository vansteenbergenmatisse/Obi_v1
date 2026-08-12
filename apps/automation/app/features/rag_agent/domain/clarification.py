"""Ambiguity/vagueness detection (PLAN 9.2, ADR-0008 decision 1).

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

Deliberately produces only a yes/no verdict, never clarification text or options — generating the
actual clarifying question and its 2-4 concrete options is PLAN 9.3's job, once a verdict says
`is_ambiguous=True`.

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
