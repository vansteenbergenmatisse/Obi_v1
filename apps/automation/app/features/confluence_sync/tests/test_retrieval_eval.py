"""End-to-end retrieval evaluation over the indexed fixture corpus — must beat the baseline.

Baseline (manifest-order ranker): retrieval_smoke recall@5=1.000, mrr=0.750, ndcg@5=0.816;
permission is leaky (returns restricted pages to unauthorized scopes).

Phase 3 target, verified here:
  * retrieval_smoke — recall@5 stays 1.000 while mrr and ndcg improve (right page ranked first);
  * permission — no restricted page is returned to a scope that may not see it (no leak), while
    authorized access still resolves. (Plain recall is *not* the permission target: it rewards the
    leaky baseline: a restricted page counts "relevant" even to callers who must be denied.)
"""

from __future__ import annotations

from sqlalchemy import text

from app.features.evaluation import (
    datasets_dir,
    evaluate,
    load_corpus_loader,
    load_dataset,
)
from app.features.retrieval import HybridRetriever, PrincipalPermissionPolicy
from app.platform.clients import build_embedding_provider, build_reranker
from app.platform.config import Settings
from app.platform.db.engine import get_reader_sessionmaker, get_sessionmaker

from ._helpers import index_page

_DATASETS = datasets_dir()

# Baseline numbers to beat (from eval-reports/baseline.json).
_BASE_SMOKE_MRR = 0.75
_BASE_SMOKE_NDCG = 0.8155


def _index_corpus(gateway, settings: Settings) -> None:
    loader = load_corpus_loader()
    for page in loader.list_pages():
        pid = int(page["id"])
        meta = gateway.get_page_meta(pid)
        if meta is not None and meta.status == "current":
            index_page(gateway, settings, pid, meta.version_number)


def _build_policy(gateway) -> PrincipalPermissionPolicy:
    loader = load_corpus_loader()
    space_of: dict[int, int] = {}
    restrictions: dict[int, set[str]] = {}
    for page in loader.list_pages():
        pid = int(page["id"])
        space_of[pid] = int(page["spaceId"])
        principals = set(gateway.get_restrictions(pid))
        if principals:
            restrictions[pid] = principals
    return PrincipalPermissionPolicy(space_of=space_of, restrictions=restrictions)


def _retriever(gateway, settings: Settings) -> HybridRetriever:
    # Reads run as the non-owner rag_reader (RLS-subject), like production.
    embedder = build_embedding_provider(settings)
    return HybridRetriever(
        get_reader_sessionmaker(), embedder, _build_policy(gateway), build_reranker(settings)
    )


def test_smoke_maintains_recall_and_beats_ranking(gateway, settings: Settings) -> None:
    _index_corpus(gateway, settings)
    retr = _retriever(gateway, settings)
    dataset = load_dataset(_DATASETS / "retrieval_smoke.json")

    report = evaluate(dataset, lambda q, s: retr.retrieve(q, s, k=5), now_iso="phase3", k=5)
    agg = report.aggregates

    assert agg["recall@5"] == 1.0  # recall maintained
    assert agg["mrr"] > _BASE_SMOKE_MRR  # right page ranked higher than baseline
    assert agg["ndcg@5"] > _BASE_SMOKE_NDCG


def test_permission_no_leak_and_authorized_access(gateway, settings: Settings) -> None:
    _index_corpus(gateway, settings)
    policy = _build_policy(gateway)
    retr = HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(settings),
        policy,
        build_reranker(settings),
    )
    dataset = load_dataset(_DATASETS / "permission.json")

    for case in dataset.cases:
        returned = retr.retrieve(case.question, case.scope, k=5)
        for pid in returned:
            assert policy.allowed(int(pid), case.scope), f"{case.id} leaked page {pid}"

    # authorized principal still retrieves the restricted page it is entitled to
    alice = retr.retrieve("What are the production deploy steps?", "acct-alice", k=5)
    assert "1002" in alice  # acct-alice is on 1002's read list
    assert "2002" not in alice  # 2002 (HR/finance) must never leak to acct-alice

    # unauthorized scope is denied the restricted page the baseline would leak
    outsider = retr.retrieve(
        "Show me the exact expense approval amounts.", "unauthorized-user", k=5
    )
    assert "2002" not in outsider


def test_rls_default_deny_on_reader_role(gateway, settings: Settings) -> None:
    """RLS alone (bare SELECT, no app-level source filter) enforces default-deny on the reader.

    Proves the policy, not just the explicit WHERE: an unset/empty or wrong scope returns zero
    rows to the non-owner role; only the matching source_id makes the rows visible.
    """
    _index_corpus(gateway, settings)
    with get_reader_sessionmaker()() as s:

        def count_with_scope(scope: str) -> int:
            s.execute(text("SELECT set_config('app.allowed_sources', :v, true)"), {"v": scope})
            return int(s.execute(text("SELECT count(*) FROM chunk")).scalar_one())

        assert count_with_scope("") == 0  # unset/empty -> default-deny
        assert count_with_scope("confluence:other") == 0  # wrong source -> zero
        assert count_with_scope("confluence:default") > 0  # matching source -> visible


def test_retriever_wrong_source_scope_returns_zero(gateway, settings: Settings) -> None:
    """End-to-end: a retriever scoped to the wrong source returns nothing (RLS + source filter)."""
    _index_corpus(gateway, settings)
    policy = _build_policy(gateway)
    question = "How do I request access to core systems when I join?"

    ok = _retriever(gateway, settings)
    assert ok.retrieve(question, "100", k=5)  # correct default source -> rows

    wrong = HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(settings),
        policy,
        build_reranker(settings),
        allowed_sources=("confluence:nonexistent",),
    )
    assert wrong.retrieve(question, "100", k=5) == []  # wrong source -> zero


def test_retrieval_writes_one_query_trace_row(gateway, settings: Settings) -> None:
    """3.5.4: a traced retrieval writes exactly one query_trace row via the writer engine."""
    _index_corpus(gateway, settings)
    retr = HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(settings),
        _build_policy(gateway),
        build_reranker(settings),
        trace_sessionmaker=get_sessionmaker(),  # writer: RLS never blocks the insert
    )
    result = retr.retrieve("How do I request access to core systems when I join?", "100", k=5)
    assert result

    with get_sessionmaker()() as s:
        rows = s.execute(
            text(
                "SELECT raw_query, retrieved_page_ids, allowed_sources, embedding_model, "
                "reranker_model, latency_ms FROM query_trace"
            )
        ).all()

    assert len(rows) == 1
    row = rows[0]
    assert row.raw_query.startswith("How do I request access")
    assert [str(p) for p in row.retrieved_page_ids] == result  # same ids, same order
    assert list(row.allowed_sources) == ["confluence:default"]
    assert row.reranker_model == "fake"
    assert row.latency_ms >= 0
