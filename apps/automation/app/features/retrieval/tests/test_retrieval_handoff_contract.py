"""Panel r4-proceed: the stage-4 -> stage-5 hand-off shape (PLAN 0.5.3).

`HybridRetriever.retrieve_with_context` (`application/retriever.py`) is the actual top-k-producing
function; `RetrievalResult`/`RetrievedHit` are the exact DTOs the answer workflow (`rag_agent`,
stage 5) reads. This is a thin, one-line design panel ("the top-k passages, their scores, and a
coverage verdict go to answer assembly") between two features, so this test stays inside
`retrieval` (deep-importing only its own feature, per the boundary rules) and asserts the
*contract* — field presence, typing, and ordering — against what stage 5 is known to read, rather
than importing `rag_agent`'s internal prompt-assembly code (deliberately not exported at its
root; see `app/features/rag_agent/domain/prompt.py`'s module docstring and its `_EvidenceHit`
structural Protocol, which exists for exactly this decoupling reason):

* `prompt.py:214-220 build_evidence_block` reads `hit.chunk_id` (int, parent-text lookup key) and
  `hit.title` (str, the numbered evidence line).
* `answer_service.py:359-367` builds each `Citation` from `hit.page_id` (str), `hit.title` (str),
  `hit.url` (str).
* `answer_service.py:269-274` calls `decide_refusal(result.top_score, ...)` — the coverage
  verdict — where `RetrievalResult.top_score` is `hits[0].score` (a float): the caller trusts hits
  already arrive sorted best-first, it never re-sorts or re-maxes.

Existing coverage this deliberately does not duplicate: `test_refusal.py`'s `r4-weak` cases and
`test_prompt.py`/`test_answer_service.py`'s `r5-evidence` cases already exercise this hand-off
end-to-end, through the real DB-backed corpus (see `confluence_sync/tests/test_answer_workflow.py`
and `test_retrieval_eval.py`). This file is the one explicit, narrow shape contract.
"""

from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy.orm import Session

from app.features.retrieval.application import retriever as retriever_module
from app.features.retrieval.application.retriever import (
    HybridRetriever,
    RetrievalResult,
    RetrievedHit,
)
from app.features.retrieval.domain.permission import PrincipalPermissionPolicy
from app.features.retrieval.infrastructure.search_repo import RerankCandidate
from app.platform.clients import build_embedding_provider, build_reranker
from app.platform.config import Settings

_CANDIDATES: dict[int, RerankCandidate] = {
    1: RerankCandidate(
        chunk_id=101, title="Onboarding guide", source_url="https://x/1", text="alpha beta"
    ),
    2: RerankCandidate(
        chunk_id=202, title="Access policy", source_url="https://x/2", text="gamma delta"
    ),
    3: RerankCandidate(
        chunk_id=303, title="Support hours", source_url="https://x/3", text="epsilon zeta"
    ),
}


class _NullSession:
    """Never queried directly: every function that would touch it is monkeypatched below.

    Implements the context-manager protocol `HybridRetriever` uses (`with session_factory() as
    session:`) so it can stand in for a real `Session` without opening one.
    """

    def __enter__(self) -> _NullSession:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def _session_factory() -> Session:
    return cast(Session, _NullSession())


def _patch_search_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for the Postgres round trip: RRF fusion, permission and rerank stay real; only the
    SQL-issuing functions are faked, so this is a unit test (no database needed)."""
    monkeypatch.setattr(retriever_module, "apply_hnsw_gucs", lambda *a, **k: None)
    monkeypatch.setattr(retriever_module, "apply_source_scope", lambda *a, **k: None)
    monkeypatch.setattr(retriever_module, "apply_knowledge_scope", lambda *a, **k: None)
    monkeypatch.setattr(
        retriever_module,
        "keyword_search",
        lambda *a, **k: [(1, 3.0), (2, 2.0), (3, 1.0)],
    )
    monkeypatch.setattr(
        retriever_module,
        "dense_search",
        lambda *a, **k: [(2, 0.9), (1, 0.8), (3, 0.7)],
    )
    monkeypatch.setattr(
        retriever_module,
        "fetch_page_scopes",
        lambda session, page_ids: ({}, {}),  # no restrictions: every page is unrestricted
    )
    monkeypatch.setattr(
        retriever_module,
        "fetch_rerank_texts",
        lambda session, page_ids, space_id, sources=None, knowledge_scopes=None: {
            pid: _CANDIDATES[pid] for pid in page_ids if pid in _CANDIDATES
        },
    )


def _build_retriever(monkeypatch: pytest.MonkeyPatch) -> HybridRetriever:
    _patch_search_repo(monkeypatch)
    settings = Settings()
    return HybridRetriever(
        _session_factory,
        build_embedding_provider(settings),
        PrincipalPermissionPolicy(),
        build_reranker(settings),
    )


def test_r4_proceed_retrieval_output_shape_matches_what_evidence_assembly_consumes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """panel r4-proceed · substep 0.5.3
    The top-k passages, their scores, and the coverage verdict go to answer assembly: stage 4's
    `RetrievalResult`/`RetrievedHit` shape carries exactly the fields stage 5 reads (chunk_id,
    title, page_id, url, score), best-first, capped at k.
    """
    retriever = _build_retriever(monkeypatch)

    result: RetrievalResult = retriever.retrieve_with_context(
        "how do I request access", scope=None, k=2
    )

    # length <= k — "top-k passages"
    assert 0 < len(result.hits) <= 2

    # ordering by score, descending — the coverage-verdict contract: `top_score` reads hits[0]
    # without re-sorting or re-maxing, so the caller trusts this order is already best-first.
    scores = [h.score for h in result.hits]
    assert scores == sorted(scores, reverse=True)
    assert result.top_score == result.hits[0].score

    # every field stage 5 actually accesses on a hit is present and correctly typed
    for hit in result.hits:
        assert isinstance(hit, RetrievedHit)
        assert isinstance(hit.page_id, str)  # Citation.page_id
        assert isinstance(hit.chunk_id, int)  # build_evidence_block's parent_texts lookup key
        assert isinstance(hit.title, str) and hit.title  # build_evidence_block's "[n] <title>"
        assert isinstance(hit.url, str)  # Citation.url
        assert isinstance(hit.score, float)  # decide_refusal's top_score / coverage verdict
