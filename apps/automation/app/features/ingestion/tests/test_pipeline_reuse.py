"""Embedding reuse: only new/edited children are re-embedded (DB-free, spy embedder)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from app.features.ingestion.application.contextualizer import Contextualizer
from app.features.ingestion.application.services import IngestionServices
from app.features.ingestion.application.versioning import _resolve_children
from app.features.ingestion.domain import normalization as norm
from app.features.ingestion.domain.chunking import ChunkConfig, plan_chunks
from app.features.ingestion.domain.tokenization import TokenCounter
from app.platform.clients.confluence_client import ConfluencePageMeta
from app.platform.config import Settings

HTML_V1 = (
    "<h1>Guide</h1>"
    "<h2>Access</h2><p>Request access via the IT portal when you join the company.</p>"
    "<h2>Contacts</h2><p>Reach the platform team on Slack for any help you need.</p>"
)
HTML_V2 = HTML_V1.replace(
    "Reach the platform team on Slack for any help you need.",
    "Reach the platform team on Slack or email for any urgent help you need.",
)


class SpyEmbedder:
    model = "spy"
    dim = 8

    def __init__(self) -> None:
        self.calls = 0
        self.total_texts = 0

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        self.total_texts += len(texts)
        return [[float(len(t) % 7)] * self.dim for t in texts]


@dataclass
class OldChild:
    stable_key: bytes
    positional_key: bytes
    content_key: bytes
    retrieval_content: str
    embedding: list[float]


def _meta() -> ConfluencePageMeta:
    return ConfluencePageMeta(
        page_id=1001, space_id=100, parent_id=None, title="Guide", status="current",
        version_number=1, version_created_at=datetime.now(UTC), source_url="http://x",
    )


def _services(embedder: SpyEmbedder) -> IngestionServices:
    settings = Settings(anthropic_api_key="", contextualization_enabled=False)
    return IngestionServices(
        counter=TokenCounter(), config=ChunkConfig(),
        contextualizer=Contextualizer(settings, client=None), embedder=embedder,
    )


def _child_plans(html: str):
    plan = plan_chunks(page_id=1001, blocks=norm.normalize_body(html), config=ChunkConfig(),
                       counter=TokenCounter())
    return [c for pp in plan for c in pp.children]


def test_first_index_embeds_all_children() -> None:
    spy = SpyEmbedder()
    plans = _child_plans(HTML_V1)
    retrieval, embeddings = _resolve_children(_meta(), norm.normalize_body(HTML_V1), plans, [],
                                              _services(spy))
    assert spy.total_texts == len(plans)  # nothing to reuse on first index
    assert all(e is not None for e in embeddings)
    assert all(r for r in retrieval)


def test_reindex_identical_reuses_all_embeddings() -> None:
    spy1 = SpyEmbedder()
    plans_v1 = _child_plans(HTML_V1)
    r1, e1 = _resolve_children(_meta(), norm.normalize_body(HTML_V1), plans_v1, [], _services(spy1))
    old = [
        OldChild(p.stable_key, p.positional_key, p.content_key, r1[i], e1[i])
        for i, p in enumerate(plans_v1)
    ]

    spy2 = SpyEmbedder()
    plans_v1b = _child_plans(HTML_V1)  # identical content
    _resolve_children(_meta(), norm.normalize_body(HTML_V1), plans_v1b, old, _services(spy2))
    assert spy2.calls == 0  # every child reused; no embedding call at all


def test_edit_one_section_reembeds_only_changed_children() -> None:
    spy1 = SpyEmbedder()
    plans_v1 = _child_plans(HTML_V1)
    r1, e1 = _resolve_children(_meta(), norm.normalize_body(HTML_V1), plans_v1, [], _services(spy1))
    old = [
        OldChild(p.stable_key, p.positional_key, p.content_key, r1[i], e1[i])
        for i, p in enumerate(plans_v1)
    ]

    spy2 = SpyEmbedder()
    plans_v2 = _child_plans(HTML_V2)  # only the Contacts paragraph changed
    _resolve_children(_meta(), norm.normalize_body(HTML_V2), plans_v2, old, _services(spy2))
    # exactly the edited section's children re-embedded; the rest reused
    changed = sum(1 for p in plans_v2 if p.content_key not in {o.content_key for o in old})
    assert spy2.total_texts == changed
    assert 0 < changed < len(plans_v2)
