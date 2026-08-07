"""Ingestion services bundle — the Phase-3 pipeline dependencies, built once from settings.

Holds the token counter, chunk config, contextualizer and embedding provider so the versioning
code stays free of provider wiring. Offline/dev without a hosted key yields a Fake embedder and a
metadata-only contextualizer, so ``embedder.model`` is the *actual* producer ("fake" offline). That
value is recorded on each indexed version, so switching to a real provider later reads as an
embedding-model change and triggers the full re-embed release gate (Phase-3 task 8).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.features.ingestion.application.contextualizer import Contextualizer
from app.features.ingestion.domain.chunking import ChunkConfig
from app.features.ingestion.domain.tokenization import TokenCounter
from app.platform.clients.anthropic_client import AnthropicMessagesClient
from app.platform.clients.embeddings_client import EmbeddingProvider, build_embedding_provider
from app.platform.config import Settings


@dataclass
class IngestionServices:
    counter: TokenCounter
    config: ChunkConfig
    contextualizer: Contextualizer
    embedder: EmbeddingProvider

    @property
    def embedding_model(self) -> str:
        return self.embedder.model

    @property
    def embedding_dim(self) -> int:
        return self.embedder.dim


def build_ingestion_services(settings: Settings) -> IngestionServices:
    embedder = build_embedding_provider(settings)
    anthropic: AnthropicMessagesClient | None = None
    if settings.contextualization_enabled and settings.anthropic_api_key:
        anthropic = AnthropicMessagesClient(
            api_key=settings.anthropic_api_key,
            timeout=settings.contextualization_timeout_seconds,
            max_retries=settings.contextualization_max_retries,
        )
    return IngestionServices(
        counter=TokenCounter(),
        config=ChunkConfig(),
        contextualizer=Contextualizer(settings, client=anthropic),
        embedder=embedder,
    )
