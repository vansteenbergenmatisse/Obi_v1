"""Cross-encoder reranker abstraction (LLM-CALL security tier).

One ``rerank(query, docs, top_k) -> [(page_id, score)]`` surface with interchangeable backends,
mirroring ``embeddings_client`` exactly:

* ``FakeReranker`` — identity: keeps the input order and scores by descending input rank.
  Deterministic, no key. Used in tests and as the offline-dev fallback so retrieval runs without
  a hosted key.
* ``CohereReranker`` — hosted cross-encoder over ``httpx`` (no vendor SDK), Cohere v2 ``/rerank``.
* ``LocalReranker`` — sentence-transformers ``CrossEncoder``, lazily imported (optional dep).

**Cross-encoder rerankers only — never a general chat model asked to reorder** (ADR-0005): a
cross-encoder is cheaper per candidate, deterministic enough to eval, and built for the task.

Security controls applied to every hosted call (mirroring the embeddings client):
  C4 timeout + bounded retry with backoff + a consecutive-failure circuit breaker;
  C10 a per-call abuse cap on the number of documents.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

import httpx

from app.platform.config import Settings
from app.platform.logging import get_logger

log = get_logger("reranker_client")

_RETRYABLE_STATUS = {408, 409, 429}


class RerankError(RuntimeError):
    """Unrecoverable rerank failure: bad config, retries exhausted, breaker open, abuse cap."""


class _Transient(Exception):
    """Retryable provider condition (5xx/429/timeout)."""


@runtime_checkable
class Reranker(Protocol):
    model: str

    def rerank(
        self, query: str, docs: Sequence[tuple[int, str]], top_k: int
    ) -> list[tuple[int, float]]:
        """Return ``(page_id, score)`` best-first for ``docs`` vs ``query`` (≤ ``top_k``)."""
        ...


class FakeReranker:
    """Identity reranker: preserves input order, scores by descending input rank.

    Not semantic — the point is determinism. With input ``[(a,·),(b,·),(c,·)]`` and ``top_k=2`` it
    returns ``[(a, 2.0), (b, 1.0)]``. Used in tests and offline dev so retrieval stays reproducible.
    """

    model = "fake"

    def rerank(
        self, query: str, docs: Sequence[tuple[int, str]], top_k: int
    ) -> list[tuple[int, float]]:
        n = len(docs)
        return [(page_id, float(n - i)) for i, (page_id, _text) in enumerate(docs[:top_k])]


class CohereReranker:
    """Cohere v2 ``/rerank`` cross-encoder over raw httpx (mirrors the embeddings discipline)."""

    _URL = "https://api.cohere.com/v2/rerank"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.model = settings.reranker_model
        self._key = settings.reranker_api_key
        self._timeout = settings.rerank_timeout_seconds
        self._max_retries = max(1, settings.rerank_max_retries)
        self._breaker_threshold = settings.rerank_breaker_threshold
        self._max_docs = settings.rerank_max_docs
        self._client = client or httpx.Client(timeout=self._timeout)
        self._consecutive_failures = 0

    def rerank(
        self, query: str, docs: Sequence[tuple[int, str]], top_k: int
    ) -> list[tuple[int, float]]:
        if not docs:
            return []
        if len(docs) > self._max_docs:  # C10 abuse cap
            raise RerankError(f"rerank() called with {len(docs)} docs > cap {self._max_docs}")
        if self._consecutive_failures >= self._breaker_threshold:  # C4 breaker
            raise RerankError(
                "rerank circuit breaker open after "
                f"{self._consecutive_failures} consecutive failures"
            )
        texts = [text for _page_id, text in docs]
        try:
            parsed = self._post_with_retry(query, texts, top_k)
        except RerankError:
            self._consecutive_failures += 1
            raise
        self._consecutive_failures = 0
        # Map Cohere's document indices back to page ids; Cohere returns results best-first.
        return [(docs[idx][0], score) for idx, score in parsed]

    def _post_with_retry(
        self, query: str, texts: Sequence[str], top_k: int
    ) -> list[tuple[int, float]]:
        last: Exception | None = None
        for attempt in range(self._max_retries):  # C4 bounded retry + backoff
            try:
                resp = self._client.post(
                    self._URL,
                    headers={
                        "Authorization": f"Bearer {self._key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "query": query,
                        "documents": list(texts),
                        "top_n": top_k,
                    },
                    timeout=self._timeout,
                )
                if resp.status_code in _RETRYABLE_STATUS or resp.status_code >= 500:
                    raise _Transient(f"status {resp.status_code}")
                resp.raise_for_status()
                return self._parse(resp, len(texts))
            except (httpx.TransportError, httpx.TimeoutException, _Transient) as exc:
                last = exc
                if attempt < self._max_retries - 1:
                    time.sleep(min(0.3 * 2**attempt, 4.0))
            except httpx.HTTPStatusError as exc:
                raise RerankError(f"rerank request rejected: {exc}") from exc
        raise RerankError(f"rerank request failed after {self._max_retries} attempts: {last}")

    def _parse(self, resp: httpx.Response, n: int) -> list[tuple[int, float]]:
        results = resp.json()["results"]
        out: list[tuple[int, float]] = []
        for r in results:
            idx = int(r["index"])
            if not 0 <= idx < n:
                raise RerankError(f"cohere returned out-of-range index {idx} for {n} docs")
            out.append((idx, float(r["relevance_score"])))
        return out


class LocalReranker:
    """sentence-transformers CrossEncoder backend (optional dependency, downloaded on first use)."""

    def __init__(self, settings: Settings) -> None:
        self.model = settings.reranker_local_model
        try:
            from sentence_transformers import (  # pyright: ignore[reportMissingImports]
                CrossEncoder,
            )
        except Exception as exc:  # pragma: no cover - optional dep
            raise RerankError(
                "RERANKER_PROVIDER=local requires sentence-transformers to be installed"
            ) from exc
        self._model = CrossEncoder(self.model)

    def rerank(  # pragma: no cover - optional dep
        self, query: str, docs: Sequence[tuple[int, str]], top_k: int
    ) -> list[tuple[int, float]]:
        if not docs:
            return []
        scores = self._model.predict([(query, text) for _page_id, text in docs])
        ranked = sorted(
            ((page_id, float(score)) for (page_id, _t), score in zip(docs, scores, strict=True)),
            key=lambda pair: pair[1],
            reverse=True,
        )
        return ranked[:top_k]


def build_reranker(settings: Settings, client: httpx.Client | None = None) -> Reranker:
    """Select a reranker from settings. Offline dev / an empty key falls back to Fake.

    ``""``/``fake`` -> Fake; ``local`` -> CrossEncoder; ``cohere`` -> hosted, unless the key is
    missing in an offline env (then Fake, so CI stays deterministic even with a live key in .env).
    """
    provider = (settings.reranker_provider or "").lower()

    if provider in ("", "fake"):
        return FakeReranker()
    if provider == "local":
        return LocalReranker(settings)
    if provider == "cohere":
        if not settings.reranker_api_key:
            if settings.is_offline_env():
                log.warning("reranker_key_missing_using_fake", provider=provider, env=settings.env)
                return FakeReranker()
            raise RerankError(f"cohere reranker requires an API key in env={settings.env}")
        return CohereReranker(settings, client=client)

    raise RerankError(f"unknown reranker provider: {settings.reranker_provider!r}")
