"""External client capability: the platform's outbound gateways.

Public surface for the small, cohesive set of external-service clients the
features consume — Confluence (live + fixture), Anthropic messages, and the
embedding providers. Only the symbols that cross the package boundary are
exported; concrete HTTP providers, transient-error types, and helpers stay
internal until a real external consumer needs them.

Unlike `platform/db` (a large, intrinsically-namespaced ORM vocabulary that is
deliberately imported by full submodule path — see ADR-0003), this package is a
handful of client contracts and factories, so a single flat root reads cleanly.

Internal rule: modules inside this package import each other by full submodule
path (e.g. `fixture_confluence_client` -> `confluence_client`), never through
this root — importing your own half-built package root raises ImportError.
"""

from __future__ import annotations

from .anthropic_client import (
    AnthropicError,
    AnthropicMessagesClient,
    cached_system_block,
)
from .confluence_client import (
    ConfluenceGateway,
    ConfluencePageMeta,
    HttpConfluenceClient,
)
from .embeddings_client import EmbeddingProvider, build_embedding_provider
from .fixture_confluence_client import FixtureConfluenceGateway
from .reranker_client import Reranker, RerankError, build_reranker

__all__ = [
    "AnthropicError",
    "AnthropicMessagesClient",
    "cached_system_block",
    "ConfluenceGateway",
    "ConfluencePageMeta",
    "HttpConfluenceClient",
    "EmbeddingProvider",
    "build_embedding_provider",
    "FixtureConfluenceGateway",
    "Reranker",
    "build_reranker",
    "RerankError",
]
