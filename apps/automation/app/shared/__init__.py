"""Shared role: stable cross-feature primitives with no clearer owner.

Contract:
- Code here MUST NOT import `app.features.*` or `app.platform.*`. Shared is the
  bottom of the dependency graph; anything that needs a feature or a platform
  capability does not belong here.
- Keep it to stable contracts, validation, constants, and pure utilities.

Current inhabitant: `hashing` — stdlib-only content/JSON hashing helpers used by
both features (ingestion, confluence_sync) and platform (embeddings client).
"""
