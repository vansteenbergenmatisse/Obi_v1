"""AnthropicMessagesClient: retry/backoff, circuit breaker (C4), input abuse cap (C10)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.platform.clients.anthropic_client import (
    AnthropicError,
    AnthropicMessagesClient,
    ImageBlock,
)


def _ok_transport() -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda r: httpx.Response(200, json={"content": [{"type": "text", "text": "hi"}]})
    )


def test_create_message_happy_path() -> None:
    client = AnthropicMessagesClient(api_key="k", client=httpx.Client(transport=_ok_transport()))
    assert client.create_message(model="m", user_text="hello", max_tokens=10) == "hi"


def test_missing_key_raises_without_tripping_breaker() -> None:
    client = AnthropicMessagesClient(api_key="", breaker_threshold=1)
    for _ in range(3):
        with pytest.raises(AnthropicError, match="not set"):
            client.create_message(model="m", user_text="hello")


def test_input_abuse_cap_rejects_oversized_prompt() -> None:
    client = AnthropicMessagesClient(
        api_key="k", client=httpx.Client(transport=_ok_transport()), max_input_chars=10
    )
    with pytest.raises(AnthropicError, match="exceeds cap"):
        client.create_message(model="m", user_text="x" * 11)
    # under the cap still works
    assert client.create_message(model="m", user_text="short") == "hi"


def test_circuit_breaker_opens_after_consecutive_failures() -> None:
    failing = httpx.MockTransport(lambda r: httpx.Response(500, json={}))
    client = AnthropicMessagesClient(
        api_key="k",
        client=httpx.Client(transport=failing),
        max_retries=1,
        breaker_threshold=2,
    )
    for _ in range(2):
        with pytest.raises(AnthropicError, match="rejected|attempts"):
            client.create_message(model="m", user_text="hello")
    # breaker now open — fails fast, without attempting the request
    with pytest.raises(AnthropicError, match="circuit breaker open"):
        client.create_message(model="m", user_text="hello")


def test_create_message_with_images_puts_image_blocks_before_text() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"content": [{"type": "text", "text": "hi"}]})

    client = AnthropicMessagesClient(
        api_key="k", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    out = client.create_message(
        model="m",
        user_text="what is this?",
        images=[ImageBlock(media_type="image/png", data="ZmFrZQ==")],
    )

    assert out == "hi"
    content = seen[0]["messages"][0]["content"]
    assert content == [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": "ZmFrZQ=="},
        },
        {"type": "text", "text": "what is this?"},
    ]


def test_create_message_without_images_keeps_the_original_single_text_block_shape() -> None:
    """No behavior change for the existing text-only call sites — content stays a one-item list."""
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"content": [{"type": "text", "text": "hi"}]})

    client = AnthropicMessagesClient(
        api_key="k", client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    client.create_message(model="m", user_text="hello")

    assert seen[0]["messages"][0]["content"] == [{"type": "text", "text": "hello"}]


def test_success_resets_the_breaker() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(500, json={})
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})

    client = AnthropicMessagesClient(
        api_key="k",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=1,
        breaker_threshold=2,  # one failure alone must not open the breaker
    )
    with pytest.raises(AnthropicError):
        client.create_message(model="m", user_text="hello")
    # a fresh call succeeds and resets the failure counter — the breaker does not stay open
    assert client.create_message(model="m", user_text="hello") == "ok"
    assert client.create_message(model="m", user_text="hello") == "ok"
