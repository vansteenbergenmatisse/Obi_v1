"""Root pytest configuration.

Runs before any app module is imported, so it can shrink the embedding dimension for the test
suite (3072-dim vectors through HNSW make DB tests ~30x slower) and force the offline Fake
embedding provider. Production is unaffected — this file is only loaded by pytest. Values use
``setdefault`` so an explicit env override still wins.
"""

from __future__ import annotations

import os

# FAIL-CLOSED default (gap CFG-A): Settings.env now defaults to "" (treated as PRODUCTION) instead
# of "local", so the suite must opt into an offline env EXPLICITLY or every Settings() would fire
# the platform-trust guard against the committed placeholder registry. "test" is in _OFFLINE_ENVS.
# setdefault so an explicit shell/CI `ENV` still wins; a real env var also outranks the root .env.
os.environ.setdefault("ENV", "test")
os.environ.setdefault("EMBEDDING_DIM", "256")
os.environ.setdefault("EMBEDDING_PROVIDER", "fake")
os.environ.setdefault("EMBEDDING_MODEL", "fake")
os.environ.setdefault("CONTEXTUALIZATION_ENABLED", "false")
# .env carries RERANKER_PROVIDER=cohere + a live key with ENV=local; the offline fallback fires
# only on an *empty* key, so without this the suite would hit Cohere non-deterministically. A real
# env var outranks the .env file in pydantic-settings, so this pins the deterministic FakeReranker.
os.environ.setdefault("RERANKER_PROVIDER", "fake")
# PLAN 11.1c: tolerate an empty Obi platform registry in the suite so unrelated tests never
# depend on knowledge-base/config/platforms.json having entries (the real file is validated by its
# own tests).
os.environ.setdefault("ALLOW_EMPTY_PLATFORMS", "true")
# substep 1.2.3: pin the registry to the in-repo default so the suite never depends on a developer's
# root .env PLATFORMS_PATH (settings reads ../.env, which may point at another checkout). An empty
# value in os.environ outranks the .env file -> Settings falls back to DEFAULT_PLATFORMS_PATH under
# knowledge-base/config/. An explicit shell export still wins (setdefault).
os.environ.setdefault("PLATFORMS_PATH", "")
