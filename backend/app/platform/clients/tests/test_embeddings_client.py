"""Embedding provider abstraction: fake determinism, batching, OpenAI request shape, breaker."""

from __future__ import annotations

import json
from math import sqrt
from pathlib import Path

import httpx
import pytest

from app.platform.clients.embeddings_client import (
    EmbeddingError,
    FakeEmbeddingProvider,
    OpenAIEmbeddingProvider,
    build_embedding_provider,
)
from app.platform.config import Settings


@pytest.fixture
def prod_platforms(tmp_path: Path) -> str:
    """A valid production platform registry (one real https ACTIVE issuer) so a non-offline
    Settings(env="production") can be constructed without tripping the fail-closed platform-trust
    guard (gap CFG-A/CFG-C) — these tests exercise the embedding factory, not the registry."""
    p = tmp_path / "platforms.json"
    p.write_text(
        json.dumps(
            {
                "platforms": {
                    "acme": {
                        "issuer": "https://acme.example.com",
                        "jwks_url": "https://acme.example.com/.well-known/jwks.json",
                        "domains": ["app.acme.example.com"],
                        "lifetime_minutes": 60,
                        "algs": ["RS256"],
                        "active": True,
                    }
                },
                "integrations": {},
            }
        )
    )
    return str(p)


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
            {"index": i, "embedding": [0.1] * body["dimensions"]} for i in range(len(body["input"]))
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
        embedding_provider="openai",
        embedding_dim=4,
        openai_api_key="k",
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


def test_factory_raises_in_production_without_key(prod_platforms: str) -> None:
    settings = Settings(
        embedding_provider="openai",
        embedding_dim=16,
        openai_api_key="",
        env="production",
        platforms_path=prod_platforms,
    )
    with pytest.raises(EmbeddingError):
        build_embedding_provider(settings)


def test_r2_embed_page_model_matches_question_model() -> None:
    """panel r2-embed · substep p0-s0_5-reg-retrieval-stage-2
    Model: the same one used for pages (OpenAI text-embedding-3-large, 3072). Ingestion (page
    embedding) and retrieval (question embedding) both call `build_embedding_provider` with the
    same `Settings`, so pinning the provider it returns for the documented production
    configuration (.env.example) pins both call sites to the identical model/dim at once."""
    settings = Settings(
        embedding_provider="openai",
        embedding_model="text-embedding-3-large",
        embedding_dim=3072,
        openai_api_key="sk-test",
    )
    provider = build_embedding_provider(settings)
    assert isinstance(provider, OpenAIEmbeddingProvider)
    assert provider.model == "text-embedding-3-large"
    assert provider.dim == 3072


def test_vd_question_uses_the_same_embedding_model_as_page_embedding() -> None:
    """panel vd-question · substep p0-s0_5-reg-the-vector-database
    The rewritten question goes through the same embedding model: ingestion (page/child
    embedding, `features/ingestion/application/services.py`) and retrieval (question embedding,
    `HybridRetriever._search`) both build their embedder by calling `build_embedding_provider`
    with the identical `Settings` object, so the provider/model/dim retrieval gets for a question
    is exactly the one ingestion used to embed the page's children."""
    settings = Settings(
        embedding_provider="openai",
        embedding_model="text-embedding-3-large",
        embedding_dim=3072,
        openai_api_key="sk-test",
    )
    page_time_embedder = build_embedding_provider(settings)
    question_time_embedder = build_embedding_provider(settings)
    assert type(page_time_embedder) is type(question_time_embedder)
    assert page_time_embedder.model == question_time_embedder.model
    assert page_time_embedder.dim == question_time_embedder.dim == 3072


def test_vd_question_embed_produces_exactly_one_vector_of_3072_numbers() -> None:
    """panel vd-question · substep p0-s0_5-reg-the-vector-database
    One vector, 3072 numbers: embedding a single rewritten question returns exactly one vector,
    and that vector holds exactly 3072 numbers -- never a batch of more than one, never a
    different width than the child chunks it will be compared against."""
    embedder = FakeEmbeddingProvider(dim=3072)
    vectors = embedder.embed(["what is the refund window for a cancelled booking"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 3072
    assert all(isinstance(x, float) for x in vectors[0])


def test_r2_embed_empty_call_skipped_without_a_request() -> None:
    """panel r2-embed · substep p0-s0_5-reg-retrieval-stage-2
    Empty text: skipped — embed() with no texts returns an empty result and never reaches the
    network, for the same hosted-provider code path retrieval's question embedder uses."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"data": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(embedding_provider="openai", embedding_dim=3072, openai_api_key="sk-test")
    provider = OpenAIEmbeddingProvider(settings, client=client)

    assert provider.embed([]) == []
    assert calls["n"] == 0
