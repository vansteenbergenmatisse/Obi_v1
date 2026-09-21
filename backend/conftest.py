"""Root pytest configuration.

Runs before any app module is imported, so it can shrink the embedding dimension for the test
suite (3072-dim vectors through HNSW make DB tests ~30x slower) and force the offline Fake
embedding provider. Production is unaffected — this file is only loaded by pytest. Values use
``setdefault`` so an explicit env override still wins.
"""

from __future__ import annotations

import os

os.environ.setdefault("EMBEDDING_DIM", "256")
os.environ.setdefault("EMBEDDING_PROVIDER", "fake")
os.environ.setdefault("EMBEDDING_MODEL", "fake")
os.environ.setdefault("CONTEXTUALIZATION_ENABLED", "false")
# .env carries RERANKER_PROVIDER=cohere + a live key with ENV=local; the offline fallback fires
# only on an *empty* key, so without this the suite would hit Cohere non-deterministically. A real
# env var outranks the .env file in pydantic-settings, so this pins the deterministic FakeReranker.
os.environ.setdefault("RERANKER_PROVIDER", "fake")
# PLAN 11.1c: tolerate an empty Obi platform registry in the suite so unrelated tests never
# depend on config/platforms.json having entries (the real file is validated by its own tests).
os.environ.setdefault("ALLOW_EMPTY_PLATFORMS", "true")
