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
from collections.abc import Sequence

import pytest
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

from ._helpers import index_page, restricted_principals

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest

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


def test_s_acl_no_restriction_recorded_is_open_to_everyone(gateway, settings: Settings) -> None:
    """panel s-acl · substep 0.5.3
    ADR-0005: a page with zero ``page_restriction`` rows (no principal recorded) is open to
    everyone — absence of restriction is never treated as deny. Indexed alone, so it is the only
    candidate any query can surface: if the permission filter ever flipped "no restriction" to
    closed, none of these callers would get anything back.
    """
    index_page(gateway, settings, 1001, 3)
    assert restricted_principals(1001) == set()  # no page_restriction rows persisted

    retr = _retriever(gateway, settings)
    question = "How do I request access to core systems when I join?"
    for principal in ("acct-alice", "someone-with-no-claims-at-all", "unauthorized-user"):
        assert "1001" in retr.retrieve(question, principal, k=5), (
            f"unrestricted page 1001 was withheld from {principal!r}"
        )


def test_s_acl_unexpandable_group_denies_everyone(gateway, settings: Settings) -> None:
    """panel s-acl · substep 0.5.3
    ADR-0005: a page whose only restriction is an unresolvable group is excluded from candidates
    for every caller at retrieval time — including one whose real claims happen to match the
    group's membership, since that membership could not be verified when access was checked.
    """
    # Force the group resolver to find nobody, as if the live lookup failed or the group has no
    # visible members — the same fail-closed path `_resolve_read_restriction` takes with no
    # resolver at all (covered at sync time by test_confluence_client.py; this proves the
    # persisted sentinel is actually honored at retrieval time, not just written correctly).
    gateway.set_group_members("grp-security", [])
    index_page(gateway, settings, 3009, 1)
    # "__unresolved_group_restriction__" is confluence_client.GROUP_RESTRICTED_SENTINEL.
    assert restricted_principals(3009) == {"__unresolved_group_restriction__"}

    retr = _retriever(gateway, settings)
    question = "Security Runbook restricted to leads only"
    # acct-frank/acct-grace are grp-security's real members per the group_members.json fixture —
    # unresolved here, so they must be denied exactly like a total outsider.
    for principal in ("acct-frank", "acct-grace", "acct-alice", "unauthorized-user"):
        assert "3009" not in retr.retrieve(question, principal, k=5), (
            f"unresolvable-group page 3009 leaked to {principal!r}"
        )


class _SpyReranker:
    """Identity reranker (same contract as ``FakeReranker``) that also records every ``(page_id,
    text)`` pair handed to ``rerank()`` — so a test can assert what the reranker actually saw,
    not just the final output."""

    model = "fake"

    def __init__(self) -> None:
        self.seen_page_ids: list[int] = []

    def rerank(
        self, query: str, docs: Sequence[tuple[int, str]], top_k: int
    ) -> list[tuple[int, float]]:
        self.seen_page_ids.extend(pid for pid, _text in docs)
        n = len(docs)
        return [(pid, float(n - i)) for i, (pid, _text) in enumerate(docs[:top_k])]


def test_s_acl_filter_runs_before_rerank_in_the_app_on_candidates(
    gateway, settings: Settings
) -> None:
    """panel s-acl · substep p0-s0_5-reg-security (Protect)
    The page ACL filter (ADR-0005) runs before rerank, in the application layer, on the fused
    candidate set — not as a database-only filter (row security alone still lets the reader role
    see the restricted page's chunks) and not after rerank (the reranker's input never includes
    the restricted page's text at all).
    """
    _index_corpus(gateway, settings)
    policy = _build_policy(gateway)
    spy = _SpyReranker()
    retr = HybridRetriever(
        get_reader_sessionmaker(), build_embedding_provider(settings), policy, spy
    )

    question = "Show me the exact expense approval amounts."
    result = retr.retrieve(question, "unauthorized-user", k=5)
    assert "2002" not in result  # final output: page 2002 (HR/finance) is denied

    # Not a database-only filter: page 2002's own chunk rows are visible to the reader role once
    # only lock 0/1 (source-scope / knowledge-scope RLS) is applied -- row security alone does not
    # exclude it. The exclusion above is therefore application-layer (lock 3), not the database.
    with get_reader_sessionmaker()() as s:
        s.execute(
            text("SELECT set_config('app.allowed_sources', :v, true)"),
            {"v": "confluence:default"},
        )
        s.execute(text("SELECT set_config('app.allowed_knowledge_scopes', '*', true)"))
        raw_count = int(
            s.execute(text("SELECT count(*) FROM chunk WHERE page_id = 2002")).scalar_one()
        )
    assert raw_count > 0

    # Not after rerank: the restricted page's text never even reached the reranker's input --
    # the filter ran on the candidate set before the rerank() call, not as a post-hoc drop.
    assert 2002 not in spy.seen_page_ids


def test_s_permitted_denied_row_text_never_reaches_reranker(gateway, settings: Settings) -> None:
    """panel s-permitted · substep p0-s0_5-reg-security (Protect)
    Only rows that passed every lock (source scope, knowledge scope, page ACL) are ever turned
    into text for the reranker: a denied page's text is never fetched, so it can never leak into
    the reranker's (or, downstream, the generator's) input -- proven by recording exactly which
    page ids the reranker received.
    """
    _index_corpus(gateway, settings)
    policy = _build_policy(gateway)
    spy = _SpyReranker()
    retr = HybridRetriever(
        get_reader_sessionmaker(), build_embedding_provider(settings), policy, spy
    )

    # acct-alice is entitled to 1002 (grp-engineering/acct-alice/acct-bob) but not to 2002
    # (grp-hr/grp-finance/acct-carol) -- both pages are indexed, so both are real candidates.
    result = retr.retrieve("What are the production deploy steps?", "acct-alice", k=5)
    assert "1002" in result

    # the permitted page's text reached the reranker...
    assert 1002 in spy.seen_page_ids
    # ...but the denied page's text never did, in this or any other traced call so far.
    assert 2002 not in spy.seen_page_ids

    outsider_spy = _SpyReranker()
    outsider = HybridRetriever(
        get_reader_sessionmaker(), build_embedding_provider(settings), policy, outsider_spy
    )
    outsider.retrieve("Show me the exact expense approval amounts.", "unauthorized-user", k=5)
    # confirmed again for a caller with zero entitlement to the restricted page: its text is
    # never converted and never handed to the reranker, even when it is the best lexical match.
    assert 2002 not in outsider_spy.seen_page_ids


def test_s_permitted_trace_records_allowed_sources_and_knowledge_scopes(
    gateway, settings: Settings
) -> None:
    """panel s-permitted · substep p0-s0_5-reg-security (Protect)
    Duplicates test_retrieval_writes_one_query_trace_row's allowed_sources proof and
    test_query_trace_records_allowed_knowledge_scopes's allowed_knowledge_scopes proof
    (test_retrieval_knowledge_scope.py) under this panel's own name: the trace row for a scoped
    query records exactly which sources and which knowledge scopes were allowed for it.
    """
    _index_corpus(gateway, settings)
    with get_sessionmaker()() as s:
        s.execute(text("UPDATE chunk SET tags = ARRAY['obi-permitted-test'] WHERE page_id = 1002"))
        s.commit()

    retr = HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(settings),
        _build_policy(gateway),
        build_reranker(settings),
        trace_sessionmaker=get_sessionmaker(),
        enable_knowledge_scope_filtering=True,
    )
    result = retr.retrieve_with_context(
        "What are the production deploy steps?",
        "acct-alice",
        k=5,
        knowledge_scopes=["obi-permitted-test"],
    )
    assert result.trace_id is not None

    with get_sessionmaker()() as s:
        row = s.execute(
            text(
                "SELECT allowed_sources, allowed_knowledge_scopes FROM query_trace WHERE id = :id"
            ),
            {"id": result.trace_id},
        ).one()

    assert list(row.allowed_sources) == ["confluence:default"]
    assert list(row.allowed_knowledge_scopes) == ["obi-permitted-test"]


def test_rls_default_deny_on_reader_role(gateway, settings: Settings) -> None:
    """panel r3-deny · substep p0-s0_5-reg-retrieval-stage-3
    A forgotten scope leaks nothing: a bug that drops the ``set_config`` call leaves
    ``current_setting('app.allowed_sources', true)`` NULL, ``string_to_array(NULL, ',')`` NULL,
    and ``source_id = ANY(NULL)`` never true — zero rows, not every row. Proves the policy itself,
    not just an explicit empty-string WHERE clause: a genuinely never-set GUC on a brand-new
    reader-role session (the real "dropped the call" bug) returns zero rows, and so does an
    explicit empty/wrong scope; only the matching source_id makes rows visible.
    """
    _index_corpus(gateway, settings)

    # The literal bug the panel describes: nobody ever calls set_config in this transaction at
    # all (not even with an empty string) — current_setting(..., true) is genuinely NULL.
    with get_reader_sessionmaker()() as fresh:
        never_set = int(fresh.execute(text("SELECT count(*) FROM chunk")).scalar_one())
    assert never_set == 0  # forgotten call -> NULL GUC -> default-deny, not a leak

    with get_reader_sessionmaker()() as s:

        def count_with_scope(scope: str) -> int:
            s.execute(text("SELECT set_config('app.allowed_sources', :v, true)"), {"v": scope})
            return int(s.execute(text("SELECT count(*) FROM chunk")).scalar_one())

        assert count_with_scope("") == 0  # explicit empty -> default-deny
        assert count_with_scope("confluence:other") == 0  # wrong source -> zero
        assert count_with_scope("confluence:default") > 0  # matching source -> visible


def test_s_source_fails_closed_with_no_guc_set(gateway, settings: Settings) -> None:
    """panel s-source · substep p0-s0_5-reg-security
    ADR-0004/0013 Lock 1 fails closed: with no ``app.allowed_sources`` set for this reader-role
    transaction, the populated ``chunk`` table returns zero rows, never every row. A fresh
    ``rag_reader`` session that never calls ``set_config`` sees ``current_setting(...)`` as NULL,
    so ``source_id = ANY(NULL)`` is never true — default-deny, not a leak of the whole corpus."""
    _index_corpus(gateway, settings)
    with get_sessionmaker()() as owner:
        total = int(owner.execute(text("SELECT count(*) FROM chunk")).scalar_one())
    assert total > 0  # the corpus is genuinely populated, so a leak would be visible

    with get_reader_sessionmaker()() as s:
        no_guc = int(s.execute(text("SELECT count(*) FROM chunk")).scalar_one())
    assert no_guc == 0


def test_r3_source_no_guc_returns_zero_rows(gateway, settings: Settings) -> None:
    """panel r3-source · substep p0-s0_5-reg-retrieval-stage-3
    No GUC: 0 rows. A fresh reader-role session with ``app.allowed_sources`` never set reads
    the ``chunk`` table under RLS and gets nothing back — the exact first check
    ``verify-isolation`` runs live (``scripts/setup_supabase.py::verify_isolation``)."""
    _index_corpus(gateway, settings)
    with get_reader_sessionmaker()() as s:
        no_guc = int(s.execute(text("SELECT count(*) FROM chunk")).scalar_one())
    assert no_guc == 0


def test_r3_source_real_source_returns_all_rows(gateway, settings: Settings) -> None:
    """panel r3-source · substep p0-s0_5-reg-retrieval-stage-3
    Real source: all rows. The reader's GUC set to the real, matching ``source_id`` reads back
    every row the owner (writer, RLS-exempt by ownership) sees — the exact second check
    ``verify-isolation`` runs live. The knowledge-scope GUC is opted out with the ``'*'``
    sentinel (mirroring ``scripts/setup_supabase.py::verify_isolation``) so the separate,
    RESTRICTIVE ``chunk_scope_read`` policy (ADR-0014, tested elsewhere under ``r3-deny``)
    does not also filter this source-axis count."""
    _index_corpus(gateway, settings)
    with get_sessionmaker()() as owner:
        total = int(owner.execute(text("SELECT count(*) FROM chunk")).scalar_one())
    assert total > 0  # the fixture corpus actually indexed something

    with get_reader_sessionmaker()() as s:
        s.execute(
            text("SELECT set_config('app.allowed_sources', :v, true)"),
            {"v": "confluence:default"},
        )
        s.execute(text("SELECT set_config('app.allowed_knowledge_scopes', '*', true)"))
        scoped = int(s.execute(text("SELECT count(*) FROM chunk")).scalar_one())
    assert scoped == total  # matching source -> every row, not a subset


def test_r3_source_bogus_source_returns_zero_rows(gateway, settings: Settings) -> None:
    """panel r3-source · substep p0-s0_5-reg-retrieval-stage-3
    Bogus source: 0 rows. The reader's GUC set to a non-matching ``source_id`` reads nothing
    back, even though the corpus is populated — the exact third check ``verify-isolation``
    runs live."""
    _index_corpus(gateway, settings)
    with get_reader_sessionmaker()() as s:
        s.execute(
            text("SELECT set_config('app.allowed_sources', :v, true)"),
            {"v": "confluence:__nonexistent__"},
        )
        bogus = int(s.execute(text("SELECT count(*) FROM chunk")).scalar_one())
    assert bogus == 0


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
