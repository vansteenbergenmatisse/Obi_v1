"""Minimal Anthropic Messages client over httpx (no vendor SDK dependency).

Used for Phase-3 chunk contextualization (cheap model) and, later, routing/answers. Supports
prompt caching on system blocks so a page's document context is billed once and reused across all
its chunks. Applies the LLM-CALL controls: finite timeout and bounded retry with backoff.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

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


class AnthropicMessagesClient:
    def __init__(
        self,
        *,
        api_key: str,
        timeout: float = 30.0,
        max_retries: int = 2,
        client: httpx.Client | None = None,
    ) -> None:
        self._key = api_key
        self._timeout = timeout
        self._max_retries = max(1, max_retries)
        self._client = client or httpx.Client(timeout=timeout)

    def create_message(
        self,
        *,
        model: str,
        user_text: str,
        system_blocks: Sequence[dict] | None = None,
        max_tokens: int = 256,
    ) -> str:
        """Return the concatenated text of the assistant reply. Raises AnthropicError on failure."""
        if not self._key:
            raise AnthropicError("ANTHROPIC_API_KEY is not set")
        body: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": [{"type": "text", "text": user_text}]}],
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
