"""Cross-encoder reranker: fake determinism, Cohere request/response shape, breaker, factory."""

from __future__ import annotations

import json

import httpx
import pytest

from app.platform.clients.reranker_client import (
    CohereReranker,
    FakeReranker,
    Reranker,
    RerankError,
    build_reranker,
)
from app.platform.config import Settings

_DOCS = [(1001, "onboarding guide"), (1002, "deploy steps"), (2002, "expense policy")]


def test_fake_is_deterministic_order_preserving_and_truncates() -> None:
    r = FakeReranker()
    a = r.rerank("q", _DOCS, top_k=2)
    b = r.rerank("q", _DOCS, top_k=2)
    assert a == b  # deterministic
    assert [pid for pid, _ in a] == [1001, 1002]  # input order preserved
    assert a[0][1] > a[1][1]  # scores descend
    # top_k only truncates; scores derive from full input length, so k=3 and k=10 both return all 3
    assert r.rerank("q", _DOCS, top_k=10) == [(1001, 3.0), (1002, 2.0), (2002, 1.0)]
    assert len(r.rerank("q", _DOCS, top_k=1)) == 1


def test_fake_empty_input() -> None:
    assert FakeReranker().rerank("q", [], top_k=5) == []


def test_fake_satisfies_the_reranker_protocol() -> None:
    assert isinstance(FakeReranker(), Reranker)


def test_cohere_sends_v2_shape_and_maps_indices_back_to_page_ids() -> None:
    seen: list[dict] = []
    seen_auth: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        seen_auth.append(request.headers.get("authorization", ""))
        # Cohere returns results best-first by relevance; index points into the input documents.
        return httpx.Response(
            200,
            json={
                "results": [
                    {"index": 2, "relevance_score": 0.91},
                    {"index": 0, "relevance_score": 0.55},
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(
        reranker_provider="cohere", reranker_model="rerank-v3.5", reranker_api_key="co-test"
    )
    ranked = CohereReranker(settings, client=client).rerank("how do I deploy?", _DOCS, top_k=2)

    assert ranked == [(2002, 0.91), (1001, 0.55)]  # index 2 -> page 2002, index 0 -> page 1001
    assert seen[0]["model"] == "rerank-v3.5"
    assert seen[0]["query"] == "how do I deploy?"
    assert seen[0]["documents"] == ["onboarding guide", "deploy steps", "expense policy"]
    assert seen[0]["top_n"] == 2
    assert seen_auth[0] == "Bearer co-test"


def test_cohere_breaker_opens_after_threshold() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500, json={"error": "boom"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    settings = Settings(
        reranker_provider="cohere",
        reranker_api_key="co-test",
        rerank_max_retries=1,
        rerank_breaker_threshold=2,
    )
    reranker = CohereReranker(settings, client=client)
    for _ in range(2):
        with pytest.raises(RerankError):
            reranker.rerank("q", _DOCS, top_k=2)
    # third call short-circuits on the open breaker without another HTTP attempt
    with pytest.raises(RerankError):
        reranker.rerank("q", _DOCS, top_k=2)
    assert calls["n"] == 2


def test_cohere_abuse_cap_rejects_oversized_call() -> None:
    settings = Settings(reranker_provider="cohere", reranker_api_key="k", rerank_max_docs=2)
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"results": []}))
    )
    with pytest.raises(RerankError):
        CohereReranker(settings, client=client).rerank("q", _DOCS, top_k=2)


def test_factory_returns_fake_for_empty_or_fake_provider() -> None:
    assert isinstance(build_reranker(Settings(reranker_provider="")), FakeReranker)
    assert isinstance(build_reranker(Settings(reranker_provider="fake")), FakeReranker)


def test_factory_falls_back_to_fake_offline_without_key() -> None:
    settings = Settings(reranker_provider="cohere", reranker_api_key="", env="local")
    assert isinstance(build_reranker(settings), FakeReranker)


def test_factory_raises_in_production_without_key() -> None:
    settings = Settings(reranker_provider="cohere", reranker_api_key="", env="production")
    with pytest.raises(RerankError):
        build_reranker(settings)


def test_factory_builds_cohere_with_key() -> None:
    settings = Settings(reranker_provider="cohere", reranker_api_key="co-test", env="production")
    assert isinstance(build_reranker(settings), CohereReranker)
