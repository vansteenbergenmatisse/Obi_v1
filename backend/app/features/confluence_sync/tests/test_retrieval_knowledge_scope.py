"""PLAN 10.4: retrieval-time knowledge-scope filtering, proven against the real DB.

Mirrors `test_retrieval_eval.py::test_permission_no_leak_and_authorized_access`'s style: index the
real fixture corpus, then prove a hard structural boundary — a chunk tagged for one knowledge scope
must never be returned to a caller whose allowed scopes don't include it, while a matching scope
still resolves it. Tags are stamped directly via SQL rather than through the label pipeline (PLAN
10.2's own tests already cover label -> tag resolution) so this stays focused on the retrieval-side
predicate alone. Also proves the flag-off default is a true no-op, and that the 0007 migration's
`ix_chunk_tags_gin` (PLAN 10.3) is plan-usable, closing 10.3's own deferred acceptance criterion.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.features.retrieval import HybridRetriever, PrincipalPermissionPolicy
from app.platform.clients import build_embedding_provider, build_reranker
from app.platform.config import Settings
from schema.engine import get_reader_sessionmaker, get_sessionmaker
from schema.models import KIND_CHILD, QueryTrace

from ._helpers import index_page

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest

_ONBOARDING_PAGE = 1001  # space 100, unrestricted
_EXPENSE_PAGE = 2001  # space 200, unrestricted


def _set_chunk_tags(page_id: int, tags: list[str]) -> None:
    with get_sessionmaker()() as s:
        s.execute(
            text("UPDATE chunk SET tags = :tags WHERE page_id = :pid"),
            {"tags": tags, "pid": page_id},
        )
        s.commit()


def _retriever() -> HybridRetriever:
    settings = Settings()
    return HybridRetriever(
        get_reader_sessionmaker(),
        build_embedding_provider(settings),
        PrincipalPermissionPolicy(),
        build_reranker(settings),
        trace_sessionmaker=get_sessionmaker(),
    )


def _set_chunk_labels(page_id: int, labels: list[str]) -> None:
    with get_sessionmaker()() as s:
        s.execute(
            text("UPDATE chunk SET labels = :labels WHERE page_id = :pid"),
            {"labels": labels, "pid": page_id},
        )
        s.commit()


def test_label_hard_filter_excludes_a_page_outside_the_connection_boxes(
    gateway, settings: Settings
) -> None:
    """ADR-routing-labels-sole-content-axis (supersedes the ADR-db-level-customer-scope-isolation-backstop knowledge-scope RLS backstop): content isolation is the
    routing-label hard filter. A page whose only routing label sits outside a chat's four
    connection boxes is never returned, while a session whose boxes include that label resolves it
    (so the exclusion is the label boundary, not an unfindable page). The retired scope backstop no
    longer participates; source/company isolation (chunk_source_read) is unchanged."""
    index_page(gateway, settings, _ONBOARDING_PAGE, 3)
    _set_chunk_labels(_ONBOARDING_PAGE, ["mews-to-pos"])
    retr = _retriever()

    # a Toast->Mews connection (boxes: obi-general, toast-general, mews-general, toast-to-pms)
    # never sees a page whose only label is mews-to-pos (the opposite direction's box)
    excluded = retr.retrieve(
        "Onboarding Guide",
        "100",
        k=5,
        session_labels=["obi-general", "toast-general", "mews-general", "toast-to-pms"],
    )
    assert str(_ONBOARDING_PAGE) not in excluded

    # a connection whose boxes include mews-to-pos does resolve it (exclusion is the label boundary)
    included = retr.retrieve(
        "Onboarding Guide", "100", k=5, session_labels=["obi-general", "mews-to-pos"]
    )
    assert str(_ONBOARDING_PAGE) in included


def test_no_knowledge_scopes_argument_is_unrestricted(gateway, settings: Settings) -> None:
    """A caller passing no `knowledge_scopes` (the internal/eval path) sets the '*' wildcard, so the
    RLS backstop does not restrict — the legacy `retrieve()` contract is preserved. The public path
    passes no scope list either since the knowledge-scope axis was retired, so it also sets '*'.
    """
    index_page(gateway, settings, _ONBOARDING_PAGE, 3)
    _set_chunk_tags(_ONBOARDING_PAGE, ["obi-mews-test"])
    retr = _retriever()

    hits = retr.retrieve("Onboarding Guide", "100", k=5)  # no knowledge_scopes

    assert str(_ONBOARDING_PAGE) in hits


def test_scope_filter_retired_knowledge_scopes_no_longer_excludes(
    gateway, settings: Settings
) -> None:
    # ADR-routing-labels-sole-content-axis: the knowledge-scope filter is RETIRED. Passing `knowledge_scopes` no longer excludes
    # a page by its `tags` — the arg is ignored (the scope GUC is opted out to wildcard). Content
    # isolation is now the routing-label axis (see retrieval/test_label_hardfilter_db.py) + source
    # isolation. This test guards against re-introducing scope-tag exclusion.
    index_page(gateway, settings, _ONBOARDING_PAGE, 3)
    _set_chunk_tags(_ONBOARDING_PAGE, ["mews-general"])
    retr = _retriever()

    baseline = retr.retrieve("Onboarding Guide", "100", k=5)
    assert str(_ONBOARDING_PAGE) in baseline

    # a scope list that does NOT include the page's tag no longer excludes it (scope axis retired).
    filtered = retr.retrieve(
        "Onboarding Guide", "100", k=5, knowledge_scopes=["obi-general", "toast-general"]
    )
    assert str(_ONBOARDING_PAGE) in filtered


def test_flag_on_includes_page_when_its_scope_is_allowed(gateway, settings: Settings) -> None:
    index_page(gateway, settings, _ONBOARDING_PAGE, 3)
    _set_chunk_tags(_ONBOARDING_PAGE, ["obi-mews-test"])
    retr = _retriever()

    hits = retr.retrieve(
        "Onboarding Guide", "100", k=5, knowledge_scopes=["obi-general-test", "obi-mews-test"]
    )

    assert str(_ONBOARDING_PAGE) in hits


def test_scope_filter_retired_no_longer_isolates_by_scope(gateway, settings: Settings) -> None:
    # ADR-routing-labels-sole-content-axis: scope tags no longer isolate content. A mews-tagged page is now visible regardless
    # of the knowledge_scopes passed (the axis is retired); cross-integration isolation is enforced
    # by the routing-label hard filter (test_label_hardfilter_db.py), not by scope tags.
    index_page(gateway, settings, _ONBOARDING_PAGE, 3)
    index_page(gateway, settings, _EXPENSE_PAGE, 4)
    _set_chunk_tags(_ONBOARDING_PAGE, ["mews-general"])
    _set_chunk_tags(_EXPENSE_PAGE, ["toast-general"])
    retr = _retriever()

    mews_view = retr.retrieve(
        "Onboarding Guide", "100", k=5, knowledge_scopes=["obi-general", "mews-general"]
    )
    assert str(_ONBOARDING_PAGE) in mews_view

    toast_view = retr.retrieve(
        "Onboarding Guide", "100", k=5, knowledge_scopes=["obi-general", "toast-general"]
    )
    assert str(_ONBOARDING_PAGE) in toast_view  # scope axis retired -> no longer excluded


def test_scope_filter_retired_untagged_chunk_still_participates(
    gateway, settings: Settings
) -> None:
    # ADR-routing-labels-sole-content-axis: with the scope axis retired, a chunk's `tags` no longer gate retrieval, so an
    # untagged chunk participates normally (membership is the routing-label axis at ingestion, and
    # retrieval filters on source + labels, never `tags`).
    index_page(gateway, settings, _ONBOARDING_PAGE, 3)
    _set_chunk_tags(_ONBOARDING_PAGE, [])  # no scope tag at all
    retr = _retriever()

    baseline = retr.retrieve("Onboarding Guide", "100", k=5)
    assert str(_ONBOARDING_PAGE) in baseline

    filtered = retr.retrieve("Onboarding Guide", "100", k=5, knowledge_scopes=["obi-general"])
    assert str(_ONBOARDING_PAGE) in filtered  # scope axis retired -> tags no longer gate


def test_query_trace_records_no_knowledge_scopes_after_retirement(
    gateway, settings: Settings
) -> None:
    # ADR-routing-labels-sole-content-axis: the scope axis is retired, so the retriever no longer sets a scope list; the trace
    # records None for allowed_knowledge_scopes (source scope + labels are the live axes).
    index_page(gateway, settings, _ONBOARDING_PAGE, 3)
    _set_chunk_tags(_ONBOARDING_PAGE, ["obi-general", "mews-general"])
    retr = _retriever()

    result = retr.retrieve_with_context("Onboarding Guide", "100", k=5)

    assert result.trace_id is not None
    with get_sessionmaker()() as s:
        row = s.get(QueryTrace, result.trace_id)
        assert row is not None
        assert row.allowed_knowledge_scopes is None


def _one_child_and_parent(page_id: int) -> tuple[int, int, str]:
    """A child chunk id, its parent chunk id, and the parent's verbatim display_content."""
    with get_sessionmaker()() as s:
        row = s.execute(
            text(
                "SELECT id, parent_chunk_id FROM chunk "
                "WHERE page_id = :p AND kind = :k AND parent_chunk_id IS NOT NULL LIMIT 1"
            ),
            {"p": page_id, "k": KIND_CHILD},
        ).one()
        parent_text = s.execute(
            text("SELECT display_content FROM chunk WHERE id = :i"),
            {"i": int(row.parent_chunk_id)},
        ).scalar_one()
    return int(row.id), int(row.parent_chunk_id), str(parent_text)


def test_auth7_label_filtered_search_excludes_out_of_box_child_so_parent_not_expanded(
    gateway, settings: Settings
) -> None:
    """gap AUTH-7 · ADR-routing-labels-sole-content-axis (supersedes the ADR-db-level-customer-scope-isolation-backstop scope version) — the load-bearing
    parent-expansion protection, now on the routing-label axis.

    Parent expansion (`fetch_parent_texts`) is only ever called on chunk ids that already passed
    the label-filtered search. So the real boundary is upstream: a child whose routing label sits
    outside the chat's connection boxes is never returned by the search, meaning its parent is
    never even requested for expansion. Here the onboarding page is labelled `mews-to-pos` only; a
    Toast->Mews session (boxes: obi-general/toast-general/mews-general/toast-to-pms) excludes it
    (its child id is absent from the hits fed to `fetch_parent_texts`), while a session whose boxes
    include that label still finds it (so the exclusion is the label boundary, not an unfindable
    page)."""
    index_page(gateway, settings, _ONBOARDING_PAGE, 3)
    _set_chunk_labels(_ONBOARDING_PAGE, ["mews-to-pos"])
    retr = _retriever()

    baseline = retr.retrieve_with_context(
        "Onboarding Guide", "100", k=5, session_labels=["obi-general", "mews-to-pos"]
    )
    assert str(_ONBOARDING_PAGE) in baseline.page_ids  # genuinely indexed and findable in-box

    toast_mews = retr.retrieve_with_context(
        "Onboarding Guide",
        "100",
        k=5,
        session_labels=["obi-general", "toast-general", "mews-general", "toast-to-pms"],
    )
    assert str(_ONBOARDING_PAGE) not in toast_mews.page_ids  # excluded before any parent expansion
    # the out-of-box child id is therefore never among the ids handed to parent expansion
    with get_sessionmaker()() as s:
        out_of_box_child_ids = {
            int(r[0])
            for r in s.execute(
                text("SELECT id FROM chunk WHERE page_id = :p AND kind = 1 AND is_active"),
                {"p": _ONBOARDING_PAGE},
            )
        }
    assert not (set(h.chunk_id for h in toast_mews.hits) & out_of_box_child_ids)


def test_auth7_parent_text_fetch_opts_out_of_scope_rls_by_design_adr0014(
    gateway, settings: Settings
) -> None:
    """gap AUTH-7 · ADR-db-level-customer-scope-isolation-backstop — pins the DELIBERATE scope-RLS opt-out on parent-text fetch (FINDING).

    `HybridRetriever.fetch_parent_texts` sets the knowledge-scope GUC to the `'*'` wildcard, so the
    RESTRICTIVE `chunk_scope_read` policy does NOT re-filter the parent by scope: an
    already-authorized child's parent is grounded on regardless of the parent's own tag. This test
    constructs the (only) scenario where a parent carries a DIFFERENT scope tag than its child —
    impossible through normal ingestion, where a page's parent and child share the page's tags — and
    confirms the parent text IS surfaced. This is by design (see the `fetch_parent_texts` docstring:
    re-filtering by scope would risk dropping a legitimately authorized parent), and is safe because
    the sibling test above guarantees only authorized children's ids ever reach this method. Pinned
    so any future change to parent-fetch scoping (tighter OR looser) is caught — a finding, not a
    defect."""
    index_page(gateway, settings, _ONBOARDING_PAGE, 3)
    child_id, parent_id, parent_text = _one_child_and_parent(_ONBOARDING_PAGE)
    with get_sessionmaker()() as s:
        s.execute(
            text("UPDATE chunk SET tags = ARRAY['obi-mews-test'] WHERE id = :i"), {"i": child_id}
        )
        s.execute(
            text("UPDATE chunk SET tags = ARRAY['obi-toast-test'] WHERE id = :i"), {"i": parent_id}
        )
        s.commit()
    retr = _retriever()

    # The child is authorized (mews); its parent carries a different (toast) tag. Because parent
    # fetch opts out of scope RLS ('*'), the parent text is still returned for the authorized child.
    result = retr.fetch_parent_texts([child_id])
    assert child_id in result
    assert result[child_id] == parent_text  # differently-tagged parent IS surfaced (ADR-db-level-customer-scope-isolation-backstop)


def test_gin_index_is_plan_usable_for_tags_overlap(gateway, settings: Settings) -> None:
    """Closes 10.3's own deferred acceptance criterion now that a `tags && ...` predicate exists.
    The fixture corpus is far too small for the planner to prefer the GIN index on cost alone (the
    other `is_active`-partial btree indexes win on a handful of rows) — this proves the index is
    *usable* for the real query shape, not that it wins under real cardinality (no invented scale
    numbers). The competing indexes are dropped inside this session's own uncommitted transaction
    only: `Session.close()` below rolls them back without a `commit()`, so nothing persists.
    """
    index_page(gateway, settings, _ONBOARDING_PAGE, 3)
    _set_chunk_tags(_ONBOARDING_PAGE, ["obi-mews-test"])

    with get_sessionmaker()() as s:
        s.execute(text("SET LOCAL enable_seqscan = off"))
        s.execute(text("DROP INDEX ix_chunk_active_space"))
        s.execute(text("DROP INDEX ix_chunk_active_source"))
        rows = s.execute(
            text(
                "EXPLAIN SELECT id FROM chunk "
                "WHERE is_active AND tags && ARRAY['obi-mews-test']::text[]"
            )
        ).fetchall()
        plan = "\n".join(str(row[0]) for row in rows)

    assert "ix_chunk_tags_gin" in plan
