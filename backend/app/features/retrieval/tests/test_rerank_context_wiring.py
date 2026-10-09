"""panel mi-rerank · substep 8.3.2 — the reranker learns who is asking.

Mirrors ``test_permission_filter.py``'s pattern: ``search_repo``'s SQL-issuing functions are
faked (no database), RRF fusion and the real permission policy stay live, and a spy reranker
captures the exact ``(query, docs)`` the cross-encoder is handed — so the assertions prove the
enrichment wiring in ``application/retriever.py`` without a hosted call.

Eligibility is enforced in SQL before this point (8.3.1); these tests prove 8.3.2 only
*reorders* the already-eligible candidate set and never widens it: the spy sees exactly the
candidates ``fetch_rerank_texts`` returned, enriched — never an extra page.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import pytest
from sqlalchemy.orm import Session

from app.features.retrieval.application import retriever as retriever_module
from app.features.retrieval.application.retriever import HybridRetriever
from app.features.retrieval.domain.applicability_match import CustomerContext
from app.features.retrieval.domain.permission import PrincipalPermissionPolicy
from app.features.retrieval.infrastructure.search_repo import RerankCandidate
from app.platform.clients.embeddings_client import FakeEmbeddingProvider

_PLATFORM_IFACE = [{"level": "platform-interface", "product": "toast", "platform": "datahub"}]
_CANDIDATES: dict[int, RerankCandidate] = {
    1: RerankCandidate(
        chunk_id=101,
        title="Toast on Data Hub",
        source_url="https://x/1",
        text="Toast on Data Hub setup guide.",
        applicability=_PLATFORM_IFACE,
    ),
    2: RerankCandidate(
        chunk_id=202,
        title="General overview",
        source_url="https://x/2",
        text="A general page with no applicability record.",
        applicability=None,
    ),
}


class _NullSession:
    def __enter__(self) -> _NullSession:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


class _SpyReranker:
    """Identity reranker that records the query and every document string it is handed."""

    model = "fake"

    def __init__(self) -> None:
        self.seen_query: str | None = None
        self.seen_docs: list[tuple[int, str]] = []

    def rerank(
        self, query: str, docs: Sequence[tuple[int, str]], top_k: int
    ) -> list[tuple[int, float]]:
        self.seen_query = query
        self.seen_docs = list(docs)
        n = len(docs)
        return [(pid, float(n - i)) for i, (pid, _t) in enumerate(docs[:top_k])]


def _wire(monkeypatch: pytest.MonkeyPatch) -> tuple[HybridRetriever, _SpyReranker]:
    monkeypatch.setattr(retriever_module, "apply_hnsw_gucs", lambda *a, **k: None)
    monkeypatch.setattr(retriever_module, "apply_source_scope", lambda *a, **k: None)
    monkeypatch.setattr(retriever_module, "apply_knowledge_scope", lambda *a, **k: None)
    monkeypatch.setattr(retriever_module, "keyword_search", lambda *a, **k: [(1, 2.0), (2, 1.0)])
    monkeypatch.setattr(retriever_module, "dense_search", lambda *a, **k: [(1, 0.9), (2, 0.8)])
    monkeypatch.setattr(retriever_module, "fetch_page_scopes", lambda s, page_ids: ({}, {}))
    monkeypatch.setattr(
        retriever_module,
        "fetch_rerank_texts",
        lambda *a, **k: {pid: _CANDIDATES[pid] for pid in _CANDIDATES},
    )
    spy = _SpyReranker()
    retriever = HybridRetriever(
        lambda: cast(Session, _NullSession()),
        FakeEmbeddingProvider(dim=8),
        PrincipalPermissionPolicy(),
        spy,
    )
    return retriever, spy


def test_rt4_rerank_sees_enriched_query_and_yaml_prefixed_docs_with_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """panel mi-rerank · substep 8.3.2
    With a verified context the reranker's query carries the context preamble and each
    document leads with a YAML applicability block ahead of its body — the matched reason
    derived from the stamped payload. A chunk with no applicability record carries no YAML
    (its body is unchanged)."""
    retriever, spy = _wire(monkeypatch)
    ctx = CustomerContext(slot_pos="toast", platform="datahub")

    result = retriever.retrieve_with_context(
        "how do I connect?", scope=None, k=5, customer_context=ctx
    )

    assert spy.seen_query is not None
    assert spy.seen_query.startswith("Customer setup:")
    assert "toast" in spy.seen_query and "datahub" in spy.seen_query
    assert spy.seen_query.endswith("how do I connect?")

    docs = dict(spy.seen_docs)
    # page 1 carries a platform-interface record -> YAML leads with the matched reason
    assert docs[1].startswith("applies-to:")
    assert "platform-interface:pos" in docs[1]
    assert "Toast on Data Hub setup guide." in docs[1]
    # page 2 has no applicability record -> body only, no YAML block
    assert not docs[2].startswith("applies-to:")
    assert docs[2] == _CANDIDATES[2].text

    # eligibility never widened: exactly the fetched candidates were scored, nothing extra
    assert {pid for pid, _ in spy.seen_docs} == {1, 2}
    assert result.page_ids == ["1", "2"]


def test_rt4_rerank_without_context_sees_bare_query_and_unenriched_docs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """panel mi-rerank · substep 8.3.2
    With no verified context the reranker sees the bare query and the bare document bodies —
    the pre-8.3.2 shape, byte-for-byte, so the fake reranker keeps zero lift and the context-
    free gold set is unmoved. This is the one change the enrichment adds: undo it (enrich the
    no-context path) and this goes red."""
    retriever, spy = _wire(monkeypatch)

    retriever.retrieve_with_context("how do I connect?", scope=None, k=5)

    assert spy.seen_query == "how do I connect?"
    docs = dict(spy.seen_docs)
    assert docs[1] == _CANDIDATES[1].text
    assert docs[2] == _CANDIDATES[2].text
