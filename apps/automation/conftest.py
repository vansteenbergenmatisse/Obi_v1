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
