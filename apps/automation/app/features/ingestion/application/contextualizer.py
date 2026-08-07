"""Contextual retrieval content (Anthropic contextual retrieval, with a deterministic fallback).

For each child chunk we build the text that gets *embedded* (``retrieval_content``), distinct from
the verbatim ``display_content`` used for citations. It always carries a factual metadata prefix
(page title + heading path). When contextualization is enabled and an Anthropic key is present, a
cheap model additionally writes a 1-2 sentence situating context using the whole page as a
prompt-cached system block (billed once per page). If the model is unavailable or errors, the chunk
degrades to the metadata-only prefix — ingestion never fails because of contextualization.

This is an LLM-CALL surface: finite timeout + bounded retry live in the client; the document
context is capped by ``contextualization_max_doc_chars`` (C10) and the whole step is disableable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.platform.clients.anthropic_client import (
    AnthropicError,
    AnthropicMessagesClient,
    cached_system_block,
)
from app.platform.config import Settings
from app.platform.logging import get_logger

log = get_logger("contextualizer")

_PROMPT = (
    "Here is a chunk taken from the document above.\n\n<chunk>\n{chunk}\n</chunk>\n\n"
    "Write a short 1-2 sentence context that situates this chunk within the overall document, "
    "using only information present in the document. Do not add facts. Answer with context only."
)


@dataclass
class ContextItem:
    title: str
    heading_path: list[str] = field(default_factory=list)
    text: str = ""


class Contextualizer:
    def __init__(self, settings: Settings, client: AnthropicMessagesClient | None = None) -> None:
        self._settings = settings
        self._enabled = settings.contextualization_enabled and bool(settings.anthropic_api_key)
        self._client = client
        self._model = settings.routing_model
        self._max_doc_chars = settings.contextualization_max_doc_chars

    def contextualize(self, *, document_text: str, items: list[ContextItem]) -> list[str]:
        """Return ``retrieval_content`` per item (order preserved)."""
        use_llm = self._enabled and self._client is not None
        doc_ctx = document_text[: self._max_doc_chars] if use_llm else ""
        system_blocks = [cached_system_block(doc_ctx)] if use_llm else None

        out: list[str] = []
        for item in items:
            prefix = _metadata_prefix(item)
            llm_ctx = ""
            if use_llm:
                llm_ctx = self._llm_context(system_blocks, item)
            out.append(_compose(prefix, llm_ctx, item.text))
        return out

    def _llm_context(self, system_blocks: list[dict] | None, item: ContextItem) -> str:
        assert self._client is not None
        try:
            return self._client.create_message(
                model=self._model,
                user_text=_PROMPT.format(chunk=item.text),
                system_blocks=system_blocks,
                max_tokens=128,
            )
        except AnthropicError as exc:
            log.warning("contextualization_failed_using_metadata_only", error=str(exc))
            return ""


def _metadata_prefix(item: ContextItem) -> str:
    parts: list[str] = []
    if item.title:
        parts.append(item.title)
    trail = " > ".join(h for h in item.heading_path if h)
    if trail and trail != item.title:
        parts.append(trail)
    return " — ".join(parts)


def _compose(prefix: str, llm_ctx: str, text: str) -> str:
    head = "\n".join(p for p in (prefix, llm_ctx) if p)
    return f"{head}\n\n{text}" if head else text
