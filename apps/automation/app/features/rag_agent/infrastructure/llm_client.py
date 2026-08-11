"""LLM-backed rewrite + generation collaborators for the answer workflow (LLM-CALL tier).

Two narrow ``Protocol``s so `AnswerService` depends on a shape, not a vendor: tests inject plain
stand-ins (no network), and a real deployment wires the Anthropic-backed classes below. The
timeout/retry/backoff/breaker/abuse-cap discipline itself lives in `AnthropicMessagesClient`
(`platform/clients/anthropic_client.py`) — these classes only add prompt assembly, PII redaction
(C6) on the fully-assembled prompt right before it is sent, and, for the rewriter, the fail-open
policy described on `AnthropicQueryRewriter`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from app.features.rag_agent.domain.pii import redact_pii
from app.features.rag_agent.domain.prompt import (
    ANSWER_SYSTEM_PROMPT,
    SMALL_TALK_SYSTEM_PROMPT,
    build_answer_prompt,
    build_rewrite_prompt,
)
from app.features.rag_agent.schemas import ChatMessage
from app.platform.clients.anthropic_client import (
    AnthropicError,
    AnthropicMessagesClient,
    cached_system_block,
)
from app.platform.logging import get_logger

log = get_logger("rag_agent.llm_client")

_REWRITE_MAX_TOKENS = 200
_ANSWER_MAX_TOKENS = 800
_SMALL_TALK_MAX_TOKENS = 150
_SMALL_TALK_FALLBACK = "Hi! I'm Obi — ask me anything about the documentation and I'll look it up."


@runtime_checkable
class QueryRewriter(Protocol):
    def rewrite(self, history: Sequence[ChatMessage]) -> str:
        """Return one standalone question from the conversation's final user turn."""
        ...


@runtime_checkable
class AnswerGenerator(Protocol):
    def generate(self, query: str, evidence_block: str) -> str:
        """Return a grounded answer citing the numbered markers in ``evidence_block``."""
        ...

    def generate_small_talk(self, query: str) -> str:
        """Return a brief, ungrounded reply to a greeting/meta message (``domain/small_talk.py``
        decides when this runs). No evidence, no citations — never a substitute for ``generate``."""
        ...


class AnthropicQueryRewriter:
    """Cheap rewrite call (``routing_model``). Single-turn history skips the call entirely.

    Fails open to the verbatim last turn on any `AnthropicError`: rewrite is an accuracy
    optimization, not the source of truth for *what the user asked* — a transient rewrite failure
    must not turn into a refusal or a crash for what would otherwise be a perfectly answerable
    query.
    """

    def __init__(self, client: AnthropicMessagesClient, model: str) -> None:
        self._client = client
        self._model = model

    def rewrite(self, history: Sequence[ChatMessage]) -> str:
        if not history:
            return ""
        if len(history) == 1:
            return history[0].content
        try:
            out = self._client.create_message(
                model=self._model,
                user_text=redact_pii(build_rewrite_prompt(history)),
                max_tokens=_REWRITE_MAX_TOKENS,
            )
        except AnthropicError:
            log.warning("query_rewrite_failed_using_verbatim", turns=len(history))
            return history[-1].content
        return out.strip() or history[-1].content


class AnthropicAnswerGenerator:
    """Grounded generation call (``answer_model``). ``generate`` errors propagate — unlike rewrite,
    there is no safe fallback *grounded* answer to fail open to; the caller (Phase 4.4's endpoint)
    decides how a generation failure surfaces to the user. ``generate_small_talk`` is different: it
    makes no factual claim and carries no accuracy risk, so it fails open to a static greeting on
    any `AnthropicError` — the same reasoning `AnthropicQueryRewriter.rewrite` uses, applied to a
    reply instead of a rewrite."""

    def __init__(self, client: AnthropicMessagesClient, model: str) -> None:
        self._client = client
        self._model = model

    def generate(self, query: str, evidence_block: str) -> str:
        return self._client.create_message(
            model=self._model,
            user_text=redact_pii(build_answer_prompt(query, evidence_block)),
            system_blocks=[cached_system_block(ANSWER_SYSTEM_PROMPT)],
            max_tokens=_ANSWER_MAX_TOKENS,
        )

    def generate_small_talk(self, query: str) -> str:
        try:
            out = self._client.create_message(
                model=self._model,
                user_text=redact_pii(query),
                system_blocks=[cached_system_block(SMALL_TALK_SYSTEM_PROMPT)],
                max_tokens=_SMALL_TALK_MAX_TOKENS,
            )
        except AnthropicError:
            log.warning("small_talk_generation_failed_using_fallback")
            return _SMALL_TALK_FALLBACK
        return out.strip() or _SMALL_TALK_FALLBACK
