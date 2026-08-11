"""Small-talk detection (pure, data-driven).

The answer runtime refuses when retrieval finds nothing relevant (``domain/refusal.py``) — correct
for a real content question, but wrong for a greeting or a meta question like "what can you do?",
neither of which was ever going to match a document. Those get a plain, ungrounded reply instead of
running the full retrieval/refusal pipeline (``AnswerService.answer``).

Deliberately a closed exact-match set, not a fuzzy/substring/LLM classifier: the *entire* normalized
message must equal one of these known-harmless phrases. A real question that happens to start with
"hi" ("hi, how do I reset my password?") does NOT match and still gets the full grounded pipeline —
erring toward running retrieval, never toward skipping it for something that might be a real
question. This also bounds the security surface of the bypass itself (``llm_client.py``'s
``generate_small_talk``): normalization only strips ordinary ASCII whitespace/punctuation, so a
message can't smuggle extra content past the exact-match check by gluing it onto a greeting.
"""

from __future__ import annotations

import re

_TRAILING_PUNCT_RE = re.compile(r"[!.?]+$")
_WHITESPACE_RE = re.compile(r"\s+")

_SMALL_TALK_PHRASES = frozenset(
    {
        # greetings
        "hi",
        "hi there",
        "hello",
        "hello there",
        "hey",
        "hey there",
        "yo",
        "howdy",
        "good morning",
        "good afternoon",
        "good evening",
        "morning",
        "evening",
        "sup",
        "what's up",
        "whats up",
        # farewells
        "bye",
        "goodbye",
        "see ya",
        "see you",
        "later",
        "take care",
        # gratitude / acknowledgement
        "thanks",
        "thank you",
        "thx",
        "ty",
        "cheers",
        "appreciate it",
        "ok",
        "okay",
        "cool",
        "nice",
        "got it",
        "sounds good",
        "alright",
        # connectivity / meta checks
        "test",
        "testing",
        "test test",
        "ping",
        "hello world",
        "are you there",
        "are you working",
        "you there",
        "anyone there",
        "is this working",
        # identity / capability questions
        "who are you",
        "what are you",
        "what can you do",
        "what can you help with",
        "what can you help me with",
        "what do you do",
        "help",
    }
)


def _normalize(text: str) -> str:
    stripped = _TRAILING_PUNCT_RE.sub("", text.strip().lower())
    return _WHITESPACE_RE.sub(" ", stripped).strip()


def is_small_talk(text: str) -> bool:
    """True iff the whole (normalized) message is a known greeting/farewell/meta phrase."""
    return _normalize(text) in _SMALL_TALK_PHRASES
