"""panel s-reader · substep 4.2 (coverage-audit gap G10)

``test_s_reader_role_usage.py`` proves on the real DB that the search transaction's session is
opened as ``rag_reader`` — but only ``keyword_search`` captures ``current_user`` there; the three
sibling reads were *inferred* to share its role. This file pins the inference's missing link, per
function: ``dense_search``, ``fetch_page_scopes`` and ``fetch_rerank_texts`` EACH receive exactly
the one session the injected (reader) session factory produced — the same session
``apply_source_scope``/``apply_knowledge_scope`` set the RLS GUCs on — never a second session from
anywhere else. Composed with the db-level role proof over that same factory, every sibling read is
independently bound to the rag_reader, GUC-configured transaction.

Spy-session unit tests mirroring ``test_torerank_handoff.py``: no database; only the SQL-issuing
``search_repo`` functions are faked; ``retrieve_with_context`` (the public entry point) runs end
to end with the real fusion and permission policy.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from sqlalchemy.orm import Session

from app.features.retrieval.application import retriever as retriever_module
from app.features.retrieval.application.retriever import HybridRetriever
from app.features.retrieval.domain.permission import PrincipalPermissionPolicy
from app.features.retrieval.infrastructure.search_repo import RerankCandidate
from app.platform.clients.embeddings_client import FakeEmbeddingProvider
from app.platform.clients.reranker_client import FakeReranker

_SIBLING_READS = ("dense_search", "fetch_page_scopes", "fetch_rerank_texts")


class _Session:
    """A distinguishable stand-in for a real transaction (context-manager protocol only); object
    identity (``is``) is what proves "same session == same role, same GUCs"."""

    def __enter__(self) -> _Session:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


@pytest.mark.parametrize("sibling", _SIBLING_READS)
def test_s_reader_sibling_read_runs_on_the_guc_bound_reader_session(
    sibling: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """panel s-reader · substep 4.2 (gap G10)
    This sibling read receives, by object identity captured in ITS OWN spy (not keyword_search's),
    the single session the reader session factory produced — the one the scope GUCs were applied
    to. Exactly one session is ever created, so the read cannot have run under another role."""
    factory_sessions: list[_Session] = []
    guc_sessions: dict[str, object] = {}
    seen: dict[str, object] = {}

    def factory() -> Session:
        s = _Session()
        factory_sessions.append(s)
        return cast(Session, s)

    monkeypatch.setattr(retriever_module, "apply_hnsw_gucs", lambda *a, **k: None)
    monkeypatch.setattr(
        retriever_module,
        "apply_source_scope",
        lambda s, sources: guc_sessions.__setitem__("apply_source_scope", s),
    )
    monkeypatch.setattr(
        retriever_module,
        "apply_knowledge_scope",
        lambda s, scopes: guc_sessions.__setitem__("apply_knowledge_scope", s),
    )

    def _keyword(s: object, *a: Any, **k: Any) -> list[tuple[int, float]]:
        seen["keyword_search"] = s
        return [(1, 1.0)]

    def _dense(s: object, *a: Any, **k: Any) -> list[tuple[int, float]]:
        seen["dense_search"] = s
        return []

    def _page_scopes(s: object, page_ids: list[int]) -> tuple[dict[int, int], dict[int, set[str]]]:
        seen["fetch_page_scopes"] = s
        return {}, {}

    def _rerank_texts(s: object, *a: Any, **k: Any) -> dict[int, RerankCandidate]:
        seen["fetch_rerank_texts"] = s
        return {1: RerankCandidate(chunk_id=11, title="t", source_url="u", text="x")}

    monkeypatch.setattr(retriever_module, "keyword_search", _keyword)
    monkeypatch.setattr(retriever_module, "dense_search", _dense)
    monkeypatch.setattr(retriever_module, "fetch_page_scopes", _page_scopes)
    monkeypatch.setattr(retriever_module, "fetch_rerank_texts", _rerank_texts)

    retriever = HybridRetriever(
        factory,
        FakeEmbeddingProvider(dim=8),
        PrincipalPermissionPolicy(),
        FakeReranker(),
    )

    retriever.retrieve_with_context("does the exact wording even matter here", scope=None, k=5)

    assert len(factory_sessions) == 1  # one reader session for the whole search transaction
    reader_session = factory_sessions[0]
    assert seen[sibling] is reader_session  # this read's OWN captured session, not an inference
    assert guc_sessions["apply_source_scope"] is reader_session
    assert guc_sessions["apply_knowledge_scope"] is reader_session
