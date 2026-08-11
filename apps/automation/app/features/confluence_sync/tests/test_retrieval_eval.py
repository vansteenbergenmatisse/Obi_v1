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

import os

from sqlalchemy import text

from app.features.evaluation import (
    datasets_dir,
    evaluate,
    evaluate_rerank_lift,
    load_corpus_loader,
    load_dataset,
    write_rerank_lift_reports,
)
from app.features.retrieval import (
    HybridRetriever,
    PrincipalPermissionPolicy,
    classify_scope,
    update_query_trace_answer,
    update_query_trace_feedback,
)
from app.platform.clients import Reranker, build_embedding_provider, build_reranker
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


def _retriever_with(gateway, settings: Settings, reranker: Reranker) -> HybridRetriever:
    """A reader-role retriever wired to a specific reranker (for before/after comparison)."""
    return HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(settings),
        _build_policy(gateway),
        reranker,
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
        space_id, principal = classify_scope(case.scope)
        for pid in returned:
            assert policy.allowed(int(pid), space_id=space_id, principal=principal), (
                f"{case.id} leaked page {pid}"
            )

    # authorized principal still retrieves the restricted page it is entitled to
    alice = retr.retrieve("What are the production deploy steps?", "acct-alice", k=5)
    assert "1002" in alice  # acct-alice is on 1002's read list
    assert "2002" not in alice  # 2002 (HR/finance) must never leak to acct-alice

    # unauthorized scope is denied the restricted page the baseline would leak
    outsider = retr.retrieve(
        "Show me the exact expense approval amounts.", "unauthorized-user", k=5
    )
    assert "2002" not in outsider


def test_permission_enforcement_is_db_backed_not_fixture_fed(gateway, settings: Settings) -> None:
    """PLAN 4.3: an EMPTY injected policy must not weaken enforcement — the retriever now reads
    ``page_source``/``page_restriction`` live per search, so a policy object carrying no data at
    all still gets the real, correct answer. This is the acceptance proof that closes the
    "fixture-only ACL" gap ADR-0004/0005 called out.
    """
    _index_corpus(gateway, settings)
    empty_policy = PrincipalPermissionPolicy()  # no space_of, no restrictions — deliberately bare
    retr = HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(settings),
        empty_policy,
        build_reranker(settings),
    )

    # authorized principal still retrieves the restricted page it is entitled to
    alice = retr.retrieve("What are the production deploy steps?", "acct-alice", k=5)
    assert "1002" in alice

    # unauthorized scope is denied the restricted page a leaky policy would return
    outsider = retr.retrieve(
        "Show me the exact expense approval amounts.", "unauthorized-user", k=5
    )
    assert "2002" not in outsider

    # space-level trust also comes from the DB (page_source.space_id), not the empty policy
    assert retr.retrieve("How do I request access to core systems when I join?", "100", k=5)


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
    """3.5.4 (+4.2): a traced retrieval writes one query_trace row with chunk ids + scores."""
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
                "reranker_model, latency_ms, retrieved_chunk_ids, rerank_scores FROM query_trace"
            )
        ).all()

    assert len(rows) == 1
    row = rows[0]
    assert row.raw_query.startswith("How do I request access")
    assert [str(p) for p in row.retrieved_page_ids] == result  # same ids, same order
    assert list(row.allowed_sources) == ["confluence:default"]
    assert row.reranker_model == "fake"
    assert row.latency_ms >= 0
    # PLAN 4.2: these were deferred/NULL at 3.5.4; retrieve() now always fills them.
    assert row.retrieved_chunk_ids is not None
    assert len(row.retrieved_chunk_ids) == len(result)
    assert row.rerank_scores is not None
    assert len(row.rerank_scores) == len(result)


def test_retrieve_with_context_surfaces_chunk_ids_scores_and_parent_text(
    gateway, settings: Settings
) -> None:
    """4.2: retrieve_with_context exposes what retrieve() discards, and its chunk ids resolve to
    real parent text via fetch_parent_texts (children retrieve, parents ground)."""
    _index_corpus(gateway, settings)
    retr = HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(settings),
        _build_policy(gateway),
        build_reranker(settings),
        trace_sessionmaker=get_sessionmaker(),
    )
    result = retr.retrieve_with_context(
        "How do I request access to core systems when I join?", "100", k=5
    )

    assert result.hits
    assert result.page_ids == [h.page_id for h in result.hits]
    assert result.top_score == result.hits[0].score
    for hit in result.hits:
        assert hit.chunk_id > 0
        assert hit.title
        assert hit.url
    assert isinstance(result.trace_id, int)

    with get_sessionmaker()() as s:
        row = s.execute(
            text("SELECT retrieved_chunk_ids, rerank_scores FROM query_trace WHERE id = :id"),
            {"id": result.trace_id},
        ).one()
    assert list(row.retrieved_chunk_ids) == [h.chunk_id for h in result.hits]
    assert list(row.rerank_scores) == [h.score for h in result.hits]

    parents = retr.fetch_parent_texts([h.chunk_id for h in result.hits])
    assert set(parents) == {h.chunk_id for h in result.hits}
    for text_ in parents.values():
        assert text_  # every child in this fixture corpus has a real parent


def test_retrieve_with_context_empty_on_no_hits(gateway, settings: Settings) -> None:
    """No candidates -> empty RetrievalResult; fetch_parent_texts([]) is a no-op, not a crash."""
    _index_corpus(gateway, settings)
    wrong = HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(settings),
        _build_policy(gateway),
        build_reranker(settings),
        allowed_sources=("confluence:nonexistent",),
    )
    result = wrong.retrieve_with_context("How do I request access?", "100", k=5)
    assert result.hits == []
    assert result.top_score is None
    assert result.trace_id is None  # no trace_sessionmaker configured
    assert wrong.fetch_parent_texts([]) == {}


def test_update_query_trace_answer_and_feedback(gateway, settings: Settings) -> None:
    """4.2/4.4: the answer runtime UPDATEs the row retrieval inserted; feedback UPDATEs it again."""
    _index_corpus(gateway, settings)
    retr = HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(settings),
        _build_policy(gateway),
        build_reranker(settings),
        trace_sessionmaker=get_sessionmaker(),
    )
    result = retr.retrieve_with_context("How do I request access to core systems?", "100", k=5)
    assert result.trace_id is not None

    with get_sessionmaker()() as s:
        update_query_trace_answer(
            s,
            result.trace_id,
            rewritten_query="How do I get access to internal systems?",
            answer="You request access via the onboarding portal [1].",
            citations=[{"marker": 1, "page_id": result.hits[0].page_id}],
        )
        update_query_trace_feedback(s, result.trace_id, 1)

    with get_sessionmaker()() as s:
        row = s.execute(
            text(
                "SELECT rewritten_query, answer, citations, feedback "
                "FROM query_trace WHERE id = :id"
            ),
            {"id": result.trace_id},
        ).one()
    assert row.rewritten_query == "How do I get access to internal systems?"
    assert row.answer == "You request access via the onboarding portal [1]."
    assert row.citations == {"markers": [{"marker": 1, "page_id": result.hits[0].page_id}]}
    assert row.feedback == 1

    # updating a nonexistent trace id is a silent no-op, not an error (defensive against a stale/
    # forged trace_id reaching PATCH /chat/{trace_id}/feedback in 4.4)
    with get_sessionmaker()() as s:
        update_query_trace_feedback(s, -1, -1)


def test_rerank_lift_before_vs_after(gateway, settings: Settings) -> None:
    """3.5.5: measure the cross-encoder's Precision@5 / NDCG@10 lift over the fixture corpus.

    'Before' is the fused, permission-filtered ranking with the order-preserving FakeReranker;
    'after' uses the configured reranker (Cohere live; Fake in CI). Retrieve depth 10 so NDCG@10
    is not truncated. In CI both are Fake, so the lift is exactly zero — the deterministic
    invariant that proves the *mechanism* without a hosted key. Set RERANKER_PROVIDER=cohere (and
    EVAL_WRITE_RERANK_REPORT=1 to persist the artifact) to capture the real lift.
    """
    _index_corpus(gateway, settings)
    dataset = load_dataset(_DATASETS / "retrieval_smoke.json")

    before_reranker = build_reranker(settings.model_copy(update={"reranker_provider": "fake"}))
    after_reranker = build_reranker(settings)
    before = _retriever_with(gateway, settings, before_reranker)
    after = _retriever_with(gateway, settings, after_reranker)

    report = evaluate_rerank_lift(
        dataset,
        before_fn=lambda q, s: before.retrieve(q, s, k=10),
        after_fn=lambda q, s: after.retrieve(q, s, k=10),
        now_iso="phase3.5.5",
        reranker_model=after_reranker.model,
    )

    assert report.case_count == len(dataset.cases)
    assert set(report.delta) == {"precision@5", "ndcg@10"}

    if after_reranker.model == "fake":
        # Identity reranker on both sides -> before == after, no lift (the CI invariant).
        assert report.before == report.after
        assert report.delta == {"precision@5": 0.0, "ndcg@10": 0.0}

    if os.environ.get("EVAL_WRITE_RERANK_REPORT"):
        write_rerank_lift_reports(report)
