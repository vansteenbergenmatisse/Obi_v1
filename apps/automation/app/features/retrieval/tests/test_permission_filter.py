"""panel r3-acl · substep p0-s0_5-reg-retrieval-stage-3

Pins the two checks the ``r3-acl`` panel names, at the level ``test_fusion_and_permission.py``'s
pure-policy tests do not reach: the live ``HybridRetriever`` pipeline. Those existing tests prove
``PrincipalPermissionPolicy.allowed()`` in isolation; these prove the *wiring* around it — that a
restricted page's text is never even handed to the reranker for an unlisted principal, and that a
page restricted to several principals (the shape a group expands to at sync time, per
``r3-groups``: "one ``page_restriction`` row per (page, account id)") is retrievable by any one of
them.

Mirrors ``test_retrieval_handoff_contract.py``'s pattern: ``search_repo``'s SQL-issuing functions
are faked (no database needed), RRF fusion, the real permission policy and the real ``FakeReranker``
stay live, so the assertions exercise the actual filter-then-rerank wiring in
``application/retriever.py:167-176``.
"""

from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy.orm import Session

from app.features.retrieval.application import retriever as retriever_module
from app.features.retrieval.application.retriever import HybridRetriever
from app.features.retrieval.domain.permission import PrincipalPermissionPolicy
from app.features.retrieval.infrastructure.search_repo import RerankCandidate
from app.platform.clients import build_embedding_provider, build_reranker
from app.platform.config import Settings

_CANDIDATES: dict[int, RerankCandidate] = {
    1: RerankCandidate(
        chunk_id=101, title="Open onboarding guide", source_url="https://x/1", text="alpha beta"
    ),
    2: RerankCandidate(
        chunk_id=202, title="Restricted HR policy", source_url="https://x/2", text="gamma delta"
    ),
}


class _NullSession:
    """Never queried directly: every function that would touch it is monkeypatched below."""

    def __enter__(self) -> _NullSession:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def _session_factory() -> Session:
    return cast(Session, _NullSession())


def _build_retriever(
    monkeypatch: pytest.MonkeyPatch, restrictions: dict[int, set[str]]
) -> tuple[HybridRetriever, list[list[int]]]:
    """Wires a retriever whose only restricted candidate set is ``restrictions``; records every
    page-id list handed to ``fetch_rerank_texts`` so a test can assert a page never appears there
    ("never reaches the reranker" is a claim about that call, not just about the final output)."""
    rerank_calls: list[list[int]] = []

    monkeypatch.setattr(retriever_module, "apply_hnsw_gucs", lambda *a, **k: None)
    monkeypatch.setattr(retriever_module, "apply_source_scope", lambda *a, **k: None)
    monkeypatch.setattr(retriever_module, "apply_knowledge_scope", lambda *a, **k: None)
    monkeypatch.setattr(retriever_module, "keyword_search", lambda *a, **k: [(1, 2.0), (2, 1.0)])
    monkeypatch.setattr(retriever_module, "dense_search", lambda *a, **k: [(1, 0.9), (2, 0.8)])
    monkeypatch.setattr(
        retriever_module,
        "fetch_page_scopes",
        lambda session, page_ids: ({}, dict(restrictions)),
    )

    def _fake_fetch_rerank_texts(
        session: object,
        page_ids: list[int],
        space_id: int | None,
        sources: object = None,
        knowledge_scopes: object = None,
    ) -> dict[int, RerankCandidate]:
        rerank_calls.append(list(page_ids))
        return {pid: _CANDIDATES[pid] for pid in page_ids if pid in _CANDIDATES}

    monkeypatch.setattr(retriever_module, "fetch_rerank_texts", _fake_fetch_rerank_texts)

    settings = Settings()
    retriever = HybridRetriever(
        _session_factory,
        build_embedding_provider(settings),
        PrincipalPermissionPolicy(),
        build_reranker(settings),
    )
    return retriever, rerank_calls


def test_r3_acl_restricted_page_never_reaches_reranker_for_unlisted_principal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """panel r3-acl · substep p0-s0_5-reg-retrieval-stage-3
    A restricted page never reaches the reranker for a principal not on its list.
    """
    retriever, rerank_calls = _build_retriever(monkeypatch, restrictions={2: {"acct-alice"}})

    result = retriever.retrieve_with_context("hr question", scope="acct-mallory", k=5)

    # the forbidden page never took a slot in the reranker's input...
    for call in rerank_calls:
        assert 2 not in call
    # ...and consequently never reached the final, permitted output.
    assert "2" not in result.page_ids
    assert result.page_ids == ["1"]


def test_r3_acl_group_restricted_page_readable_by_group_members_after_expansion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """panel r3-acl · substep p0-s0_5-reg-retrieval-stage-3
    A group-restricted page is readable by the group's members after expansion.
    """
    # Per r3-groups: a group is expanded at sync time into one page_restriction row per member
    # account id, so a "group-restricted" page is, at this layer, simply a page whose restriction
    # set holds several principal ids.
    group_members = {"acct-alice", "acct-bob", "acct-carol"}
    retriever, rerank_calls = _build_retriever(monkeypatch, restrictions={2: group_members})

    result = retriever.retrieve_with_context("hr question", scope="acct-bob", k=5)

    # a member's page id took a reranker slot...
    assert any(2 in call for call in rerank_calls)
    # ...and is in the final, permitted output.
    assert "2" in result.page_ids
