"""panel r3-torerank · substep p0-s0_5-reg-retrieval-stage-3 (Protect batch)

Regression tests locking in `HybridRetriever`'s stage-3-to-4 hand-off (`application/retriever.py`,
already working today): only candidates that survived all three locks -- lock 1 source-scope RLS,
lock 2 knowledge-scope RLS, lock 3 page ACL (see `docs/Final_docs/obi-system-brief.md` section
06.3) -- are sliced to at most `rerank_depth`, and their text is fetched next inside the *same*
transaction, under the *same* scope, as the searches that produced them.

Spy-session unit tests, no database, mirroring `test_retrieval_handoff_contract.py`: the real RRF
fusion (`domain/fusion.py`) and `PrincipalPermissionPolicy.allowed` (`domain/permission.py`) run
unmodified; only the SQL-issuing `search_repo` functions are faked, so `retrieve_with_context` (the
public entry point) is exercised end to end and the identity of the `session` object plus the
`sources`/`knowledge_scopes` values that reach `fetch_rerank_texts` can be captured for comparison
against what the searches themselves used.
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


class _Session:
    """A distinguishable stand-in for a real transaction (context-manager protocol only); object
    identity (``is``/``==`` on a set) is what proves "same session == same transaction"."""

    def __enter__(self) -> _Session:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def test_rt3_torerank_caps_at_rerank_depth_after_locks_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """panel r3-torerank · substep p0-s0_5-reg-retrieval-stage-3
    Up to rerank_depth candidates move on to the text fetch, and only *after* lock 3 (page ACL)
    has already dropped a candidate that would otherwise have fit inside the cap -- a page-ACL-
    restricted candidate never reaches the reranker, cap or no cap.
    """
    session = _Session()
    fetched_page_ids: list[int] = []

    # 12 permitted-by-fusion-order pages; page 7 is later ACL-restricted to a principal that is
    # not the caller, so both the ACL drop and the rerank_depth=5 cap must hold in the outcome.
    kw_pages = [(pid, float(20 - pid)) for pid in range(1, 13)]

    monkeypatch.setattr(retriever_module, "apply_hnsw_gucs", lambda *a, **k: None)
    monkeypatch.setattr(retriever_module, "apply_source_scope", lambda *a, **k: None)
    monkeypatch.setattr(retriever_module, "apply_knowledge_scope", lambda *a, **k: None)
    monkeypatch.setattr(retriever_module, "keyword_search", lambda *a, **k: kw_pages)
    monkeypatch.setattr(retriever_module, "dense_search", lambda *a, **k: [])
    monkeypatch.setattr(
        retriever_module,
        "fetch_page_scopes",
        lambda session, page_ids: ({}, {7: {"someone-else"}}),
    )

    def _rerank_texts(
        session: object,
        page_ids: list[int],
        space_id: int | None,
        sources: Any = None,
        knowledge_scopes: Any = None,
    ) -> dict[int, RerankCandidate]:
        fetched_page_ids.extend(page_ids)
        return {
            pid: RerankCandidate(chunk_id=pid * 10, title=f"t{pid}", source_url="u", text="x")
            for pid in page_ids
        }

    monkeypatch.setattr(retriever_module, "fetch_rerank_texts", _rerank_texts)

    retriever = HybridRetriever(
        lambda: cast(Session, session),
        FakeEmbeddingProvider(dim=8),
        PrincipalPermissionPolicy(),
        FakeReranker(),
        rerank_depth=5,
        allowed_sources=("confluence:default",),
    )

    retriever.retrieve_with_context("q", "acct-alice", k=5)

    # capped: never more than rerank_depth candidates are handed to the text fetch
    assert len(fetched_page_ids) == 5
    # lock 3 (page ACL) already ran: the restricted page never occupies a cap slot
    assert 7 not in fetched_page_ids
    # the cap keeps the highest-ranked permitted candidates, in fused rank order
    assert fetched_page_ids == [1, 2, 3, 4, 5]


def test_rt3_torerank_fetches_text_in_same_transaction_same_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """panel r3-torerank · substep p0-s0_5-reg-retrieval-stage-3
    The rerank-text fetch runs inside the exact same transaction as the searches that produced its
    candidates (one `session_factory()` call for the whole search, the same session object
    throughout), and under the exact same scope (`sources`/`knowledge_scopes`) those searches
    used -- never a second connection, and never a widened or narrowed scope.
    """
    session = _Session()
    session_factory_calls = 0
    seen_sessions: set[object] = set()
    scope_by_call: dict[str, tuple[Any, Any]] = {}

    def factory() -> Session:
        nonlocal session_factory_calls
        session_factory_calls += 1
        return cast(Session, session)

    def _keyword(
        s: object,
        query: str,
        space_id: int | None,
        limit: int,
        sources: Any = None,
        knowledge_scopes: Any = None,
    ) -> list[tuple[int, float]]:
        seen_sessions.add(s)
        scope_by_call["keyword_search"] = (sources, knowledge_scopes)
        return [(1, 1.0)]

    def _dense(
        s: object,
        vec: Any,
        space_id: int | None,
        limit: int,
        dim: int,
        sources: Any = None,
        knowledge_scopes: Any = None,
    ) -> list[tuple[int, float]]:
        seen_sessions.add(s)
        scope_by_call["dense_search"] = (sources, knowledge_scopes)
        return []

    def _page_scopes(s: object, page_ids: list[int]) -> tuple[dict[int, int], dict[int, set[str]]]:
        seen_sessions.add(s)
        return {}, {}

    def _rerank_texts(
        s: object,
        page_ids: list[int],
        space_id: int | None,
        sources: Any = None,
        knowledge_scopes: Any = None,
    ) -> dict[int, RerankCandidate]:
        seen_sessions.add(s)
        scope_by_call["fetch_rerank_texts"] = (sources, knowledge_scopes)
        return {1: RerankCandidate(chunk_id=11, title="t", source_url="u", text="x")}

    monkeypatch.setattr(retriever_module, "apply_hnsw_gucs", lambda *a, **k: None)
    monkeypatch.setattr(retriever_module, "apply_source_scope", lambda s, sources: None)
    monkeypatch.setattr(retriever_module, "apply_knowledge_scope", lambda s, scopes: None)
    monkeypatch.setattr(retriever_module, "keyword_search", _keyword)
    monkeypatch.setattr(retriever_module, "dense_search", _dense)
    monkeypatch.setattr(retriever_module, "fetch_page_scopes", _page_scopes)
    monkeypatch.setattr(retriever_module, "fetch_rerank_texts", _rerank_texts)

    retriever = HybridRetriever(
        factory,
        FakeEmbeddingProvider(dim=8),
        PrincipalPermissionPolicy(),
        FakeReranker(),
        allowed_sources=("confluence:default", "confluence:secondary"),
        enable_knowledge_scope_filtering=True,
    )

    retriever.retrieve_with_context("q", None, k=5, knowledge_scopes=["obi-mews-test"])

    # one connection for the whole stage-3 hand-off: the text fetch never opens a second session
    assert session_factory_calls == 1
    assert seen_sessions == {session}

    # the exact same scope the searches ran under is what the text fetch used
    assert scope_by_call["fetch_rerank_texts"] == scope_by_call["keyword_search"]
    assert scope_by_call["fetch_rerank_texts"] == scope_by_call["dense_search"]
    assert scope_by_call["fetch_rerank_texts"] == (
        ("confluence:default", "confluence:secondary"),
        ["obi-mews-test"],
    )
