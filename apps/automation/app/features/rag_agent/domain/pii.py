"""PII redaction (C6) for text sent to the answer runtime's Anthropic calls (PLAN 4.4).

Pattern-based, not NER — catches the common structured PII shapes (email, phone, SSN, card
number) that a user might paste into a chat query before the assembled prompt leaves the process.
Applied at the LLM-client boundary (`infrastructure/llm_client.py`), not inside `AnswerService`,
so retrieval/CRAG continue to compare the verbatim query — only the outbound Anthropic payload is
scrubbed.

Scope, stated plainly: this is a defensive net for accidental PII in the *user's* query text, not a
content-governance pass over the *retrieved Confluence evidence* (that text is first-party
corpus content the org already chose to index, the same posture `ingestion`'s C6 opt-outs take for
the embedding/contextualization calls) — though the regexes run over the whole assembled prompt, so
an accidental match inside the evidence block is caught too, as a bonus, not a guarantee.
"""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")

_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_EMAIL_RE, "[REDACTED_EMAIL]"),
    (_SSN_RE, "[REDACTED_SSN]"),
    (_CARD_RE, "[REDACTED_CARD]"),
    (_PHONE_RE, "[REDACTED_PHONE]"),
)


def redact_pii(text: str) -> str:
    """Replace common PII patterns with a labeled placeholder. Order matters: email before phone
    (an email's digits must never be re-matched as a phone number) and SSN/card before phone
    (both are more specific digit-grouping patterns than the generic phone regex)."""
    for pattern, placeholder in _REPLACEMENTS:
        text = pattern.sub(placeholder, text)
    return text
