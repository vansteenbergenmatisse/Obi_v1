"""AnthropicQueryRewriter / AnthropicAnswerGenerator: prompt assembly, PII redaction (C6) on the
outbound payload, and the rewriter's fail-open policy — against a mocked transport, no network.
"""

from __future__ import annotations

import json

import httpx

from app.features.rag_agent.infrastructure.llm_client import (
    AnthropicAnswerGenerator,
    AnthropicQueryRewriter,
)
from app.features.rag_agent.schemas import ChatMessage
from app.platform.clients.anthropic_client import AnthropicMessagesClient


def _client_capturing(seen: list[dict]) -> AnthropicMessagesClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})

    return AnthropicMessagesClient(
        api_key="k", client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_rewrite_redacts_pii_before_sending() -> None:
    seen: list[dict] = []
    rewriter = AnthropicQueryRewriter(_client_capturing(seen), "routing-model")
    history = [
        ChatMessage(role="user", content="who do I contact"),
        ChatMessage(role="assistant", content="the IT team"),
        ChatMessage(role="user", content="email me at alice@example.com when done"),
    ]
    rewriter.rewrite(history)

    sent_text = seen[0]["messages"][0]["content"][0]["text"]
    assert "alice@example.com" not in sent_text
    assert "[REDACTED_EMAIL]" in sent_text


def test_rewrite_single_turn_skips_the_call_entirely() -> None:
    seen: list[dict] = []
    rewriter = AnthropicQueryRewriter(_client_capturing(seen), "routing-model")
    out = rewriter.rewrite([ChatMessage(role="user", content="email me at a@b.com")])
    assert out == "email me at a@b.com"  # verbatim: no LLM call, nothing to redact
    assert seen == []


def test_rewrite_fails_open_to_verbatim_last_turn_on_error() -> None:
    client = AnthropicMessagesClient(
        api_key="k",
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500, json={}))),
        max_retries=1,
    )
    rewriter = AnthropicQueryRewriter(client, "routing-model")
    history = [
        ChatMessage(role="user", content="first"),
        ChatMessage(role="user", content="second turn"),
    ]
    assert rewriter.rewrite(history) == "second turn"


def test_generate_redacts_pii_and_sends_cached_system_block() -> None:
    seen: list[dict] = []
    generator = AnthropicAnswerGenerator(_client_capturing(seen), "answer-model")
    generator.generate("call 415-555-0100 for help", "[1] Source\nSome evidence")

    body = seen[0]
    sent_text = body["messages"][0]["content"][0]["text"]
    assert "415-555-0100" not in sent_text
    assert "[REDACTED_PHONE]" in sent_text
    assert body["model"] == "answer-model"
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_generate_small_talk_sends_the_small_talk_system_prompt_and_redacts_pii() -> None:
    seen: list[dict] = []
    generator = AnthropicAnswerGenerator(_client_capturing(seen), "answer-model")
    out = generator.generate_small_talk("hi, I'm alice@example.com")

    body = seen[0]
    sent_text = body["messages"][0]["content"][0]["text"]
    assert "alice@example.com" not in sent_text
    assert "[REDACTED_EMAIL]" in sent_text
    assert "no evidence was retrieved" in body["system"][0]["text"]
    assert out == "ok"  # the mocked transport's canned reply


def test_generate_small_talk_fails_open_to_a_static_greeting_on_error() -> None:
    client = AnthropicMessagesClient(
        api_key="k",
        client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500, json={}))),
        max_retries=1,
    )
    generator = AnthropicAnswerGenerator(client, "answer-model")

    out = generator.generate_small_talk("hi")

    assert "Obi" in out  # the static fallback, not a raised AnthropicError
