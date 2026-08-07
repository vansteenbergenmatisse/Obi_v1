"""Embedding provider abstraction: fake determinism, batching, OpenAI request shape, breaker."""

from __future__ import annotations

import json
from math import sqrt

import httpx
import pytest

from app.platform.clients.embeddings_client import (
    EmbeddingError,
    FakeEmbeddingProvider,
    OpenAIEmbeddingProvider,
    build_embedding_provider,
)
from app.platform.config import Settings


def _l2(v: list[float]) -> float:
    return sqrt(sum(x * x for x in v))


def test_fake_provider_is_deterministic_and_right_dim() -> None:
    p = FakeEmbeddingProvider(dim=3072)
    a = p.embed(["hello world"])
    b = p.embed(["hello world"])
    assert len(a[0]) == 3072
    assert a == b  # deterministic
    assert p.embed(["different"])[0] != a[0]
    assert abs(_l2(a[0]) - 1.0) < 1e-6  # L2-normalized


def test_fake_provider_empty_input() -> None:
    assert FakeEmbeddingProvider(dim=8).embed([]) == []


def test_openai_provider_batches_and_sends_dimensions() -> None:
    seen_requests: list[dict] = []
    seen_auth: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen_requests.append(body)
        seen_auth.append(request.headers.get("authorization", ""))
        data = [
            {"index": i, "embedding": [0.1] * body["dimensions"]}
            for i in range(len(body["input"]))
        ]
        return httpx.Response(200, json={"data": data})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(
        embedding_provider="openai",
        embedding_model="text-embedding-3-large",
        embedding_dim=3072,
        openai_api_key="sk-test",
        embedding_max_batch=2,
    )
    provider = OpenAIEmbeddingProvider(settings, client=client)
    vectors = provider.embed(["a", "b", "c"])  # 3 texts, batch size 2 -> 2 requests

    assert len(vectors) == 3
    assert all(len(v) == 3072 for v in vectors)
    assert len(seen_requests) == 2
    assert seen_requests[0]["dimensions"] == 3072
    assert seen_requests[0]["model"] == "text-embedding-3-large"
    assert seen_auth[0] == "Bearer sk-test"


def test_openai_breaker_opens_after_threshold() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"error": "boom"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(
        embedding_provider="openai",
        embedding_dim=4,
        openai_api_key="sk-test",
        embedding_max_batch=1,
        embedding_max_retries=1,
        embedding_breaker_threshold=2,
    )
    provider = OpenAIEmbeddingProvider(settings, client=client)
    with pytest.raises(EmbeddingError):
        provider.embed(["a", "b", "c", "d", "e"])
    # breaker opens at 2 consecutive failed batches -> we never attempt all 5
    assert calls["n"] < 5


def test_abuse_cap_rejects_oversized_call() -> None:
    settings = Settings(
        embedding_provider="openai", embedding_dim=4, openai_api_key="k",
        embedding_max_texts_per_call=3,
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": []}))
    )
    provider = OpenAIEmbeddingProvider(settings, client=client)
    with pytest.raises(EmbeddingError):
        provider.embed(["a", "b", "c", "d"])


def test_factory_falls_back_to_fake_offline_without_key() -> None:
    settings = Settings(
        embedding_provider="openai", embedding_dim=16, openai_api_key="", env="local"
    )
    provider = build_embedding_provider(settings)
    assert isinstance(provider, FakeEmbeddingProvider)
    assert provider.dim == 16


def test_factory_raises_in_production_without_key() -> None:
    settings = Settings(
        embedding_provider="openai", embedding_dim=16, openai_api_key="", env="production"
    )
    with pytest.raises(EmbeddingError):
        build_embedding_provider(settings)
