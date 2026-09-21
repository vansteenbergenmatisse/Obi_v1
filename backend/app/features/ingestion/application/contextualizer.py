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

from app.platform.clients import (
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

# Signal phrases that mark a *meta-refusal* — the model talking about its own lack of access to
# the document instead of writing situating context. Left un-discarded, this text is stored as
# ``retrieval_content`` and then embedded + cross-encoder-reranked (BM25 is immune), depressing the
# relevance signal below the refusal threshold and causing false "routed to a human" answers even
# when real content exists (PLAN 3b(b), observed live on the obi-*-test pages). Conservative by
# design: a false positive merely degrades to the deterministic metadata prefix (always safe),
# while a miss poisons the corpus — so we err toward discarding.
_META_REFUSAL_SIGNALS = (
    "i don't have access",
    "i do not have access",
    "i don't have the document",
    "i do not have the document",
    "without access to the",
    "i can't see the",
    "i cannot see the",
    "i can't access",
    "i cannot access",
    "i'm unable to",
    "i am unable to",
    "i don't have enough context",
    "i do not have enough context",
    # the "I cannot provide context … the document provided contains only …" family — the exact
    # phrasing seen live on the obi-*-test pages that the first signal list missed (PLAN 3b).
    "cannot provide context",
    "can't provide context",
    "provided contains only",
    "contains only the single",
    "contains only this single",
    "only see this single",
    "only this single chunk",
    "no document was provided",
    "no document is provided",
    "there is no document",
    "there's no document",
    "wasn't provided",
    "was not provided",
    "isn't provided",
    "is not provided",
    "i don't see the",
    "i do not see the",
)


def _is_meta_refusal(reply: str) -> bool:
    """True when the model reply is *about* missing document access rather than real context."""
    low = reply.strip().lower()
    return any(sig in low for sig in _META_REFUSAL_SIGNALS)


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
            reply = self._client.create_message(
                model=self._model,
                user_text=_PROMPT.format(chunk=item.text),
                system_blocks=system_blocks,
                max_tokens=128,
            )
        except AnthropicError as exc:
            log.warning("contextualization_failed_using_metadata_only", error=str(exc))
            return ""
        if _is_meta_refusal(reply):
            # Discard the meta-reply and degrade to the metadata-only prefix, same as a transport
            # failure — never let "I don't have access to the document…" become embeddable text.
            log.warning("contextualization_meta_refusal_discarded", reply=reply[:120])
            return ""
        return reply


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
