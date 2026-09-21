"""Minimal Anthropic Messages client over httpx (no vendor SDK dependency).

Used for Phase-3 chunk contextualization (cheap model) and, from Phase 4.4, the chat answer
runtime's query rewrite + grounded generation calls. Supports prompt caching on system blocks so a
page's document context is billed once and reused across all its chunks. Applies the LLM-CALL
controls: finite timeout, bounded retry with backoff, a consecutive-failure circuit breaker (C4),
and an optional per-call input-size abuse cap (C10) — the same discipline `reranker_client.py` and
`embeddings_client.py` apply to their hosted calls. The breaker/cap default to effectively-off
(a high threshold, no cap) so the existing contextualization call sites are unaffected; Phase 4.4's
chat client construction sets both explicitly, because that call sits behind an HTTP surface for
the first time. From PLAN 7.3, `create_message` also accepts optional multimodal `images`
(`ImageBlock`) content blocks for the vision-grounded image analysis call (ADR-0009).
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass

import httpx

from app.platform.logging import get_logger

log = get_logger("anthropic_client")

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_RETRYABLE_STATUS = {408, 409, 429}


class AnthropicError(RuntimeError):
    """Unrecoverable Anthropic call failure (bad config or retries exhausted)."""


class _Transient(Exception):
    pass


@dataclass(frozen=True)
class ImageBlock:
    """One inline image for a multimodal `create_message` call (PLAN 7.3, ADR-0009 decision 4).

    A platform-local shape, not `rag_agent`'s `ImageAttachment` — this module is `platform/**`
    and imports no features (repo boundary rule); callers convert their own DTO into this at the
    call site.
    """

    media_type: str
    data: str


class AnthropicMessagesClient:
    def __init__(
        self,
        *,
        api_key: str,
        timeout: float = 30.0,
        max_retries: int = 2,
        breaker_threshold: int = 1_000_000,
        max_input_chars: int | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._key = api_key
        self._timeout = timeout
        self._max_retries = max(1, max_retries)
        self._breaker_threshold = breaker_threshold
        self._max_input_chars = max_input_chars
        self._client = client or httpx.Client(timeout=timeout)
        self._consecutive_failures = 0

    def create_message(
        self,
        *,
        model: str,
        user_text: str,
        system_blocks: Sequence[dict] | None = None,
        images: Sequence[ImageBlock] | None = None,
        max_tokens: int = 256,
    ) -> str:
        """Return the concatenated text of the assistant reply. Raises AnthropicError on failure.

        ``images`` (PLAN 7.3) adds multimodal content blocks alongside ``user_text`` — the C10
        abuse cap below still only measures ``user_text`` length; per-image count/byte caps are a
        separate control (C3/C10) enforced by the caller at the request-validation boundary
        (`rag_agent/server/router.py`'s `chat_max_images_per_turn`/`chat_max_image_bytes`), not
        here, since this client has no notion of a "turn".
        """
        if not self._key:
            raise AnthropicError("ANTHROPIC_API_KEY is not set")
        if self._max_input_chars is not None and len(user_text) > self._max_input_chars:  # C10
            raise AnthropicError(
                f"create_message() input ({len(user_text)} chars) exceeds cap "
                f"{self._max_input_chars}"
            )
        if self._consecutive_failures >= self._breaker_threshold:  # C4 circuit breaker
            raise AnthropicError(
                "anthropic circuit breaker open after "
                f"{self._consecutive_failures} consecutive failures"
            )
        try:
            text = self._create_message(model, user_text, system_blocks, images, max_tokens)
        except AnthropicError:
            self._consecutive_failures += 1
            raise
        self._consecutive_failures = 0
        return text

    def _create_message(
        self,
        model: str,
        user_text: str,
        system_blocks: Sequence[dict] | None,
        images: Sequence[ImageBlock] | None,
        max_tokens: int,
    ) -> str:
        # Images precede the text block (Anthropic's own guidance for multimodal requests); a
        # call with no images keeps the exact single-text-block shape every existing call site
        # already sends, so this is additive, not a behavior change for text-only callers.
        content: list[dict] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": img.media_type, "data": img.data},
            }
            for img in (images or [])
        ]
        # An empty text block (PLAN 7.8: a genuinely text-empty, image-only turn) is rejected
        # outright by the real Anthropic API (400) — omit it rather than send an empty string;
        # an image-only content list is accepted and lets the system prompt drive the reply.
        if user_text:
            content.append({"type": "text", "text": user_text})
        body: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": content}],
        }
        if system_blocks:
            body["system"] = list(system_blocks)

        last: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = self._client.post(
                    _API_URL,
                    headers={
                        "x-api-key": self._key,
                        "anthropic-version": _API_VERSION,
                        "content-type": "application/json",
                    },
                    json=body,
                    timeout=self._timeout,
                )
                if resp.status_code in _RETRYABLE_STATUS or resp.status_code >= 500:
                    raise _Transient(f"status {resp.status_code}")
                resp.raise_for_status()
                return _extract_text(resp.json())
            except (httpx.TransportError, httpx.TimeoutException, _Transient) as exc:
                last = exc
                if attempt < self._max_retries - 1:
                    time.sleep(min(0.3 * 2**attempt, 4.0))
            except httpx.HTTPStatusError as exc:
                raise AnthropicError(f"anthropic request rejected: {exc}") from exc
        raise AnthropicError(f"anthropic request failed after {self._max_retries} attempts: {last}")


def cached_system_block(text: str) -> dict:
    """A system text block marked for prompt caching (billed once, reused across calls)."""
    return {"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}


def _extract_text(payload: dict) -> str:
    parts = [b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text"]
    return "".join(parts).strip()
