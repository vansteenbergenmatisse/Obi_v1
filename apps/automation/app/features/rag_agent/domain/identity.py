"""Identity/basic-question detection + the facts that answer it (pure, data-driven).

Companion to `domain/small_talk.py`. A question like "which integration do we use?" or "what
company am I?" is not small-talk and was never going to match a document, so the normal pipeline
retrieves nothing, scores near the reranker floor, and refuses it as `off_topic` — the wrong
behavior, because the answer is already in hand: the verified edge token (`AuthContext`,
PLAN 11.1c) carries `integration`/`company_name`/`company_id`. `AnswerService` short-circuits a
match here to a dedicated, ungrounded reply (`llm_client.generate_identity`) that is given those
facts plus an operator-editable static block, instead of running retrieval/refusal.

Deliberately a closed exact-match set, exactly like `is_small_talk`: the *entire* normalized
message must equal one of these known identity phrasings. This keeps a real documentation question
that merely shares words ("which integration guide covers webhooks", "what company holidays are
documented") on the full grounded pipeline, and bounds the security surface of the bypass — a
message can't smuggle extra content past the check by gluing it onto an identity phrase, so the
whole-message injection probe still runs normally rather than reaching this ungrounded path. The
accepted v1 tradeoff is recall: an unusual phrasing falls through to retrieval (and, today, an
off-topic redirect) rather than being answered — the same call the small-talk starter chips made.

`IdentityFacts` is a pure value the application layer builds from `AuthContext` (kept here, not
importing `AuthContext`, so this domain module has no dependency on the application layer): it is
what `build_identity_context_block` (domain/prompt.py) renders into the per-user system block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_TRAILING_PUNCT_RE = re.compile(r"[!.?]+$")
_WHITESPACE_RE = re.compile(r"\s+")

_IDENTITY_PHRASES = frozenset(
    {
        # integration / platform
        "which integration do we use",
        "what integration do we use",
        "which integration am i using",
        "what integration am i using",
        "what integration is this",
        "which platform do we use",
        "what platform do we use",
        "what platform am i on",
        "which platform am i on",
        "what is my integration",
        "what's my integration",
        "whats my integration",
        # company
        "what company am i",
        "which company am i",
        "what company is this",
        "what's my company",
        "whats my company",
        "what is my company",
        "what company do i belong to",
        "which company do i belong to",
        "which company do i work for",
        "what company do i work for",
        # self identity — "who am i" is distinct from small-talk's "who are you"
        "who am i",
    }
)


@dataclass(frozen=True, slots=True)
class IdentityFacts:
    """The per-request identity, taken verbatim from the verified token (never user-reported).

    All three fields are `None` on the tokenless/general path — the identity reply then answers
    only from the operator's static block (`build_identity_system_prompt`)."""

    integration: str | None
    company_name: str | None
    company_id: str | None

    @property
    def has_business_identity(self) -> bool:
        """True when the token carried an integration (the all-three-or-none business claim, see
        `server/token_verifier.py`) — i.e. there is a real per-user identity to state."""
        return self.integration is not None


def _normalize(text: str) -> str:
    stripped = _TRAILING_PUNCT_RE.sub("", text.strip().lower())
    return _WHITESPACE_RE.sub(" ", stripped).strip()


def is_identity_question(text: str) -> bool:
    """True iff the whole (normalized) message is a known identity/basic-question phrase."""
    return _normalize(text) in _IDENTITY_PHRASES
