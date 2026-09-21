"""Embedding provider abstraction (LLM-CALL security tier).

One ``embed(texts) -> vectors`` surface with interchangeable backends:

* ``FakeEmbeddingProvider`` — deterministic, offline, no key. Used in tests and as the local-dev
  fallback so ingestion runs without a hosted key.
* ``OpenAIEmbeddingProvider`` / ``VoyageEmbeddingProvider`` — hosted, over ``httpx`` (no vendor SDK
  dependency), matching the existing ``HttpConfluenceClient`` style.
* ``LocalEmbeddingProvider`` — sentence-transformers, lazily imported.

Security controls applied to every hosted call:
  C4 timeout + bounded retry with backoff + a consecutive-failure circuit breaker;
  C10 a per-call abuse cap and fixed batch sizing.

``security_baseline`` for these surfaces is recorded in
``app/features/ingestion/FEATURES`` / the phase report.
"""

from __future__ import annotations

import random
import time
from collections.abc import Iterator, Sequence
from math import sqrt
from typing import Protocol, runtime_checkable

import httpx

from app.platform.config import Settings
from app.platform.logging import get_logger
from app.shared.hashing import sha256_text

log = get_logger("embeddings_client")

_RETRYABLE_STATUS = {408, 409, 429}


class EmbeddingError(RuntimeError):
    """Unrecoverable embedding failure: bad config, retries exhausted, breaker open, abuse cap."""


@runtime_checkable
class EmbeddingProvider(Protocol):
    model: str
    dim: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def _chunks(items: Sequence[str], size: int) -> Iterator[Sequence[str]]:
    for i in range(0, len(items), max(1, size)):
        yield items[i : i + size]


class FakeEmbeddingProvider:
    """Deterministic pseudo-embeddings from a text hash. Not semantic — for offline dev/tests."""

    def __init__(self, dim: int, model: str = "fake") -> None:
        self.dim = dim
        self.model = model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def _vector(self, text: str) -> list[float]:
        seed = int.from_bytes(sha256_text(text)[:8], "big")
        rng = random.Random(seed)
        v = [rng.uniform(-1.0, 1.0) for _ in range(self.dim)]
        norm = sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]


class _HttpEmbeddingProvider:
    """Shared batching / retry / breaker / abuse-cap machinery for hosted providers."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.model = settings.embedding_model
        self.dim = settings.embedding_dim
        self._max_batch = settings.embedding_max_batch
        self._max_retries = max(1, settings.embedding_max_retries)
        self._breaker_threshold = settings.embedding_breaker_threshold
        self._max_texts = settings.embedding_max_texts_per_call
        self._timeout = settings.embedding_timeout_seconds
        self._client = client or httpx.Client(timeout=self._timeout)

    # --- subclass hooks -------------------------------------------------
    def _request(self, batch: Sequence[str]) -> httpx.Response:
        raise NotImplementedError

    def _parse(self, resp: httpx.Response, batch_len: int) -> list[list[float]]:
        raise NotImplementedError

    # --- public ---------------------------------------------------------
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        if len(texts) > self._max_texts:  # C10 abuse cap
            raise EmbeddingError(f"embed() called with {len(texts)} texts > cap {self._max_texts}")
        out: list[list[float]] = []
        consecutive_failures = 0
        for batch in _chunks(texts, self._max_batch):
            try:
                out.extend(self._post_with_retry(batch))
                consecutive_failures = 0
            except EmbeddingError:
                consecutive_failures += 1
                if consecutive_failures >= self._breaker_threshold:  # C4 breaker
                    raise EmbeddingError(
                        "embedding circuit breaker open after "
                        f"{consecutive_failures} consecutive batch failures"
                    ) from None
        if len(out) != len(texts):  # a batch failed without tripping the breaker
            raise EmbeddingError("embedding failed for one or more batches")
        return out

    def _post_with_retry(self, batch: Sequence[str]) -> list[list[float]]:
        last: Exception | None = None
        for attempt in range(self._max_retries):  # C4 bounded retry + backoff
            try:
                resp = self._request(batch)
                if resp.status_code in _RETRYABLE_STATUS or resp.status_code >= 500:
                    raise _Transient(f"status {resp.status_code}")
                resp.raise_for_status()
                return self._parse(resp, len(batch))
            except (httpx.TransportError, httpx.TimeoutException, _Transient) as exc:
                last = exc
                if attempt < self._max_retries - 1:
                    time.sleep(min(0.3 * 2**attempt, 4.0))
            except httpx.HTTPStatusError as exc:
                raise EmbeddingError(f"embedding request rejected: {exc}") from exc
        raise EmbeddingError(f"embedding request failed after {self._max_retries} attempts: {last}")


class _Transient(Exception):
    """Retryable provider condition (5xx/429/timeout)."""


class OpenAIEmbeddingProvider(_HttpEmbeddingProvider):
    _URL = "https://api.openai.com/v1/embeddings"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        super().__init__(settings, client)
        self._key = settings.openai_api_key

    def _request(self, batch: Sequence[str]) -> httpx.Response:
        return self._client.post(
            self._URL,
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
            json={"model": self.model, "input": list(batch), "dimensions": self.dim},
            timeout=self._timeout,
        )

    def _parse(self, resp: httpx.Response, batch_len: int) -> list[list[float]]:
        rows = sorted(resp.json()["data"], key=lambda r: r["index"])
        vectors = [r["embedding"] for r in rows]
        if len(vectors) != batch_len:
            raise EmbeddingError("OpenAI returned a mismatched number of embeddings")
        return vectors


class VoyageEmbeddingProvider(_HttpEmbeddingProvider):
    _URL = "https://api.voyageai.com/v1/embeddings"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        super().__init__(settings, client)
        self._key = settings.voyage_api_key

    def _request(self, batch: Sequence[str]) -> httpx.Response:
        return self._client.post(
            self._URL,
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
            json={"model": self.model, "input": list(batch), "output_dimension": self.dim},
            timeout=self._timeout,
        )

    def _parse(self, resp: httpx.Response, batch_len: int) -> list[list[float]]:
        rows = sorted(resp.json()["data"], key=lambda r: r["index"])
        vectors = [r["embedding"] for r in rows]
        if len(vectors) != batch_len:
            raise EmbeddingError("Voyage returned a mismatched number of embeddings")
        return vectors


class LocalEmbeddingProvider:
    """sentence-transformers backend (optional dependency, downloaded on first use)."""

    def __init__(self, settings: Settings) -> None:
        self.model = settings.embedding_model
        self.dim = settings.embedding_dim
        try:
            from sentence_transformers import (  # pyright: ignore[reportMissingImports]
                SentenceTransformer,
            )
        except Exception as exc:  # pragma: no cover - optional dep
            raise EmbeddingError(
                "EMBEDDING_PROVIDER=local requires sentence-transformers to be installed"
            ) from exc
        self._model = SentenceTransformer(self.model)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:  # pragma: no cover - optional dep
        if not texts:
            return []
        vecs = self._model.encode(list(texts), normalize_embeddings=True)
        return [list(map(float, v)) for v in vecs]


def build_embedding_provider(
    settings: Settings, client: httpx.Client | None = None
) -> EmbeddingProvider:
    """Select a provider from settings. Offline dev without a hosted key falls back to Fake."""
    provider = (settings.embedding_provider or "fake").lower()

    if provider == "fake":
        return FakeEmbeddingProvider(settings.embedding_dim, settings.embedding_model or "fake")
    if provider == "local":
        return LocalEmbeddingProvider(settings)
    if provider in ("openai", "voyage"):
        key = settings.openai_api_key if provider == "openai" else settings.voyage_api_key
        if not key:
            if settings.is_offline_env():
                log.warning(
                    "embedding_key_missing_using_fake",
                    provider=provider,
                    env=settings.env,
                )
                return FakeEmbeddingProvider(settings.embedding_dim, "fake")
            raise EmbeddingError(f"{provider} embeddings require an API key in env={settings.env}")
        cls = OpenAIEmbeddingProvider if provider == "openai" else VoyageEmbeddingProvider
        return cls(settings, client=client)

    raise EmbeddingError(f"unknown embedding provider: {settings.embedding_provider!r}")
