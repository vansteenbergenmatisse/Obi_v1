"""Phase 11.1a — the customer-isolation DB backstop
(ADR-db-level-customer-scope-isolation-backstop), read-path side.

The mews/opera/toast/general boundary was enforced *only* by an app-layer ``tags && :scopes``
predicate gated behind ``enable_knowledge_scope_filtering`` — which **failed open** (flag off, or a
single dropped predicate, returned every customer's rows to everyone). Source isolation already
fails *closed* via ADR-source-id-row-security-with-reader-writer-roles RLS; the customer axis did
not.

This adds a second, **RESTRICTIVE** RLS policy on ``chunk`` (``chunk_scope_read``) keyed on a new
per-transaction GUC ``app.allowed_knowledge_scopes``, mirroring ``app.allowed_sources``. Being
RESTRICTIVE it **ANDs** with the source policy (a second *permissive* policy would OR, weakening
isolation). Semantics:

* GUC set to a scope list -> only chunks whose ``tags`` overlap it are visible.
* GUC unset (a dropped call / bug) -> ``current_setting`` is NULL -> policy denies (fail closed).
* GUC set to the explicit sentinel ``'*'`` -> unrestricted (the internal/eval path opts out on
  purpose; the public ``/chat`` path always resolves a real scope list, never ``'*'``).

These tests read ``chunk`` directly as the non-owner ``rag_reader`` (RLS-subject; the owner is
exempt by ADR-supabase-postgres-store-without-force-rls ``NO FORCE``) with **no app-layer predicate
at all**, so they prove the DB
enforces the boundary on its own. Mirrors ``test_force_rls_managed_postgres.py``'s direct reads.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.features.retrieval import apply_knowledge_scope
from app.platform.config import Settings
from schema import engine as engine_mod
from schema import schema
from schema.engine import get_reader_sessionmaker

from ._helpers import index_page

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest

_MEWS_PAGE = 1001  # space 100, unrestricted
_OPERA_PAGE = 2001  # space 200, unrestricted
_READER_ROLE = "rag_reader"


def _set_chunk_tags(page_id: int, tags: list[str]) -> None:
    from schema.engine import get_sessionmaker

    with get_sessionmaker()() as s:
        s.execute(
            text("UPDATE chunk SET tags = :tags WHERE page_id = :pid"),
            {"tags": tags, "pid": page_id},
        )
        s.commit()


def _count_chunks(session, page_id: int) -> int:
    return session.execute(
        text("SELECT count(*) FROM chunk WHERE page_id = :p"), {"p": page_id}
    ).scalar_one()


def test_scope_rls_blocks_cross_customer_read_via_guc_alone(gateway, settings: Settings) -> None:
    """With only the scope GUC set (no app predicate), a cross-customer chunk is invisible."""
    index_page(gateway, settings, _MEWS_PAGE, 3)
    index_page(gateway, settings, _OPERA_PAGE, 3)
    _set_chunk_tags(_MEWS_PAGE, ["obi-mews-test"])
    _set_chunk_tags(_OPERA_PAGE, ["obi-operacloud-test"])

    reader = get_reader_sessionmaker()
    with reader() as s:
        s.execute(text("SET LOCAL app.allowed_sources = 'confluence:default'"))  # source ok
        s.execute(
            text("SELECT set_config('app.allowed_knowledge_scopes', 'obi-operacloud-test', true)")
        )
        mews = _count_chunks(s, _MEWS_PAGE)
        opera = _count_chunks(s, _OPERA_PAGE)

    assert mews == 0, "reader saw a cross-customer chunk with only the scope GUC -> isolation leak"
    assert opera > 0, "reader could not see its own scope's chunks -> policy over-restrictive"


def test_scope_rls_fails_closed_when_scope_guc_unset(gateway, settings: Settings) -> None:
    """A dropped/unset scope GUC denies all tagged chunks (fail closed), not returns everything."""
    index_page(gateway, settings, _MEWS_PAGE, 3)
    _set_chunk_tags(_MEWS_PAGE, ["obi-mews-test"])

    reader = get_reader_sessionmaker()
    with reader() as s:
        s.execute(text("SET LOCAL app.allowed_sources = 'confluence:default'"))
        # deliberately DO NOT set app.allowed_knowledge_scopes
        rows = _count_chunks(s, _MEWS_PAGE)

    assert rows == 0, "unset scope GUC returned rows -> fail-OPEN, the exact bug 11.1a closes"


def test_scope_rls_wildcard_is_an_explicit_opt_out(gateway, settings: Settings) -> None:
    """The '*' sentinel restores unrestricted reads for the internal/eval path (only when set)."""
    index_page(gateway, settings, _MEWS_PAGE, 3)
    _set_chunk_tags(_MEWS_PAGE, ["obi-mews-test"])

    reader = get_reader_sessionmaker()
    with reader() as s:
        s.execute(text("SET LOCAL app.allowed_sources = 'confluence:default'"))
        s.execute(text("SELECT set_config('app.allowed_knowledge_scopes', '*', true)"))
        rows = _count_chunks(s, _MEWS_PAGE)

    assert rows > 0, "'*' wildcard did not restore unrestricted reads for the opt-out path"


def test_sec_empty_tags_visible_to_no_scope(gateway, settings: Settings) -> None:
    """panel 3.4.1 · D3/D4
    An active chunk with ``tags = []`` returns for no real scope value (fail-closed floor).

    The old ``chunk_scope_read`` policy carried an ``OR cardinality(tags) = 0`` floor that made an
    untagged chunk global — a cross-scope leak the moment a page's last tag was dropped. Step 4
    (migration 0014, D3) drops that clause: empty tags overlap nothing, so an active empty-tags
    chunk is visible to *no* scope. "Public" is now the explicit ``general`` tag, never empty tags.
    The ``'*'`` opt-out (internal/eval + already-authorized parent expansion) is deliberately
    retained, so an empty-tags chunk is still returned under the wildcard — asserted here so a
    future removal of that opt-out is caught."""
    index_page(gateway, settings, _MEWS_PAGE, 3)
    _set_chunk_tags(_MEWS_PAGE, [])  # no scope tag at all

    reader = get_reader_sessionmaker()
    with reader() as s:
        s.execute(text("SET LOCAL app.allowed_sources = 'confluence:default'"))
        s.execute(
            text("SELECT set_config('app.allowed_knowledge_scopes', 'obi-operacloud-test', true)")
        )
        under_opera = _count_chunks(s, _MEWS_PAGE)
        s.execute(text("SELECT set_config('app.allowed_knowledge_scopes', 'obi-mews-test', true)"))
        under_mews = _count_chunks(s, _MEWS_PAGE)
        s.execute(text("SELECT set_config('app.allowed_knowledge_scopes', '*', true)"))
        under_wildcard = _count_chunks(s, _MEWS_PAGE)

    assert under_opera == 0, "empty-tags chunk visible under a real scope -> empty=public leak (D3)"
    assert under_mews == 0, "empty-tags chunk visible under a real scope -> empty=public leak (D3)"
    assert under_wildcard > 0, "'*' opt-out no longer returns empty-tags chunk -> eval/parent broke"


def test_sec_read_paths_use_overlap_not_equality(gateway, settings: Settings) -> None:
    """panel 3.4.1 · D3/D4
    A chunk carrying two tags is visible to a scope that overlaps one of them, not only to an exact
    match — the scope gate filters by ``tags && allowed_scopes`` overlap, never set equality.

    A ``[mews, toast]`` page is legitimate sharing (D4): a mews-only reader must see it (overlap
    true), a disjoint operacloud reader must not. Set equality (``tags = allowed_scopes``) would
    hide it from the single-scope mews reader, breaking sharing. This locks the overlap semantics at
    the RLS boundary; the app-layer read paths (dense/keyword via ``search_repo``, curated, parent)
    use the identical ``&&`` operator and are exercised behaviourally by
    ``test_sync_rules_visibility.py`` (retrieval) and ``test_curated_scope_rls_*`` (curated)."""
    index_page(gateway, settings, _MEWS_PAGE, 3)
    _set_chunk_tags(_MEWS_PAGE, ["obi-mews-test", "obi-toast-test"])  # shared across two scopes

    reader = get_reader_sessionmaker()
    with reader() as s:
        s.execute(text("SET LOCAL app.allowed_sources = 'confluence:default'"))
        s.execute(text("SELECT set_config('app.allowed_knowledge_scopes', 'obi-mews-test', true)"))
        under_mews = _count_chunks(s, _MEWS_PAGE)
        s.execute(text("SELECT set_config('app.allowed_knowledge_scopes', 'obi-toast-test', true)"))
        under_toast = _count_chunks(s, _MEWS_PAGE)
        s.execute(
            text("SELECT set_config('app.allowed_knowledge_scopes', 'obi-operacloud-test', true)")
        )
        under_opera = _count_chunks(s, _MEWS_PAGE)

    assert under_mews > 0, "shared [mews,toast] chunk hidden from mews -> equality, not overlap"
    assert under_toast > 0, "shared [mews,toast] chunk hidden from toast -> equality, not overlap"
    assert under_opera == 0, "shared [mews,toast] chunk visible to operacloud -> overlap too loose"


def test_sec_scope_guc_is_local_does_not_leak_into_next_transaction_on_same_connection(
    gateway, settings: Settings
) -> None:
    """panel 3.4.1 · substep 4.2 (coverage gap G13)
    ``apply_knowledge_scope`` sets the scope GUC with ``set_config(..., is_local=true)`` — that
    transaction-locality is what keeps a pooled connection safe: transaction 1 resolves mews and
    reads mews rows; transaction 2 on the SAME DBAPI connection, which sets nothing, must read
    ZERO rows (fail-closed unset GUC), never inherit mews's visibility. The source GUC is pinned
    session-level here ON PURPOSE, so the zero-rows outcome in transaction 2 is attributable to
    the scope GUC reverting, not to the source axis masking a leak."""
    index_page(gateway, settings, _MEWS_PAGE, 3)
    _set_chunk_tags(_MEWS_PAGE, ["obi-mews-test"])

    eng = engine_mod.get_reader_engine()
    with eng.connect() as conn:  # one checked-out connection, reused across both transactions
        s = Session(bind=conn)
        try:
            # transaction 1: source axis session-level (deliberate, see docstring), scope via the
            # production helper (is_local=true).
            s.execute(text("SELECT set_config('app.allowed_sources', 'confluence:default', false)"))
            apply_knowledge_scope(s, ["obi-mews-test"])
            rows_txn1 = _count_chunks(s, _MEWS_PAGE)
            s.commit()  # transaction 1 ends; the connection stays checked out

            # transaction 2: same connection, NOTHING set.
            rows_txn2 = _count_chunks(s, _MEWS_PAGE)
            scope_guc_txn2 = s.execute(
                text("SELECT current_setting('app.allowed_knowledge_scopes', true)")
            ).scalar()

            assert rows_txn1 > 0, "precondition: txn 1 should see its own scope's rows"
            assert rows_txn2 == 0, (
                "scope GUC visibility leaked into the next transaction on the same pooled "
                "connection -> is_local not honored (fail-open)"
            )
            assert scope_guc_txn2 in (None, ""), (
                f"scope GUC survived the transaction boundary: {scope_guc_txn2!r}"
            )
        finally:
            # Drop the deliberate session-level source GUC before the connection goes back to
            # the pool, so no later test inherits it.
            s.rollback()
            s.execute(text("RESET app.allowed_sources"))
            s.commit()
            s.close()


def test_sec_scope_element_with_embedded_comma_cannot_widen_access(
    gateway, settings: Settings
) -> None:
    """panel 3.4.1 · substep 4.2 (coverage gap G14a)
    Semantic injection on a scope VALUE: one allowed-scopes ELEMENT containing an embedded comma
    (``'obi-mews-test,obi-toast-test'`` as a single value) must not widen access to both scopes.
    The real policy splits its GUC with ``string_to_array(.., ',')``, so the DB cannot tell one
    comma'd value from two scopes — ``apply_knowledge_scope`` (the one choke point every
    production scope-GUC write funnels through: search txn, parent expansion, curated) rejects
    the element before joining, and the transaction stays fail-closed: zero rows from either
    scope, never mews+toast."""
    index_page(gateway, settings, _MEWS_PAGE, 3)
    index_page(gateway, settings, _OPERA_PAGE, 3)
    _set_chunk_tags(_MEWS_PAGE, ["obi-mews-test"])
    _set_chunk_tags(_OPERA_PAGE, ["obi-toast-test"])

    reader = get_reader_sessionmaker()
    with reader() as s:
        s.execute(text("SET LOCAL app.allowed_sources = 'confluence:default'"))
        with pytest.raises(ValueError, match="scope"):
            apply_knowledge_scope(s, ["obi-mews-test,obi-toast-test"])
        # the GUC was never set -> the RESTRICTIVE policy fails closed on both scopes.
        assert _count_chunks(s, _MEWS_PAGE) == 0, "comma'd scope value granted mews visibility"
        assert _count_chunks(s, _OPERA_PAGE) == 0, "comma'd scope value WIDENED to a second scope"


def test_sec_literal_wildcard_scope_list_cannot_unlock_opt_out(gateway, settings: Settings) -> None:
    """panel 3.4.1 · substep 4.2 (coverage gap G14b)
    A scopes list whose joined value equals the literal ``'*'`` (``["*"]`` arriving as caller
    DATA, not the intentional internal ``None`` sentinel) must not unlock the wildcard RLS
    opt-out: ``apply_knowledge_scope`` rejects the element and the transaction stays fail-closed
    (zero rows). The internal ``None`` -> ``'*'`` path (eval / already-authorized parent
    expansion) keeps working — asserted in the same session so the two can never be conflated."""
    index_page(gateway, settings, _MEWS_PAGE, 3)
    _set_chunk_tags(_MEWS_PAGE, ["obi-mews-test"])

    reader = get_reader_sessionmaker()
    with reader() as s:
        s.execute(text("SET LOCAL app.allowed_sources = 'confluence:default'"))
        with pytest.raises(ValueError, match="scope"):
            apply_knowledge_scope(s, ["*"])
        assert _count_chunks(s, _MEWS_PAGE) == 0, (
            "caller-supplied ['*'] unlocked the wildcard opt-out -> cross-customer read"
        )
        # The intentional internal sentinel is untouched: None -> '*' still opts out.
        apply_knowledge_scope(s, None)
        assert _count_chunks(s, _MEWS_PAGE) > 0, "the internal None sentinel opt-out broke"


def _seed_curated(tags_by_title: dict[str, list[str]]) -> None:
    with engine_mod.get_sessionmaker()() as s:
        for title, tags in tags_by_title.items():
            s.execute(
                text(
                    "INSERT INTO curated_knowledge_entry (tags, title, body, is_active) "
                    "VALUES (:tags, :title, :body, true)"
                ),
                {"tags": tags, "title": title, "body": f"body of {title}"},
            )
        s.commit()


def _curated_titles_visible_to_reader(scope_guc: str | None) -> set[str]:
    reader = get_reader_sessionmaker()
    with reader() as s:
        if scope_guc is not None:
            s.execute(
                text("SELECT set_config('app.allowed_knowledge_scopes', :v, true)"),
                {"v": scope_guc},
            )
        rows = s.execute(text("SELECT title FROM curated_knowledge_entry")).scalars().all()
    return set(rows)


def test_curated_scope_rls_isolates_tagged_entries_but_keeps_global(
    gateway, settings: Settings
) -> None:
    """The curated analogue of the chunk backstop (ADR-db-level-customer-scope-isolation-backstop):
    as ``rag_reader``, a curated entry
    tagged for one customer is invisible under another's scope, an empty-tags entry stays global,
    and an unset GUC fails closed for the *tagged* entries. Sets up the full post-0009/0010 curated
    RLS posture on a connection and tears it down, so the shared harness (curated RLS off) is
    unperturbed."""
    _seed_curated(
        {
            "mews entry": ["obi-mews-test"],
            "opera entry": ["obi-operacloud-test"],
            "global entry": [],  # empty tags -> every scope
        }
    )
    eng = engine_mod.get_engine()
    try:
        with eng.connect() as conn:
            schema.enable_non_chunk_rls(conn)
            schema.apply_reader_rls(conn, role=_READER_ROLE)
            schema.apply_curated_scope_rls(conn)
            conn.commit()

        opera_view = _curated_titles_visible_to_reader("obi-operacloud-test")
        assert "opera entry" in opera_view, "reader could not see its own scope's curated entry"
        assert "global entry" in opera_view, "empty-tags curated entry should be global"
        assert "mews entry" not in opera_view, "cross-customer curated entry leaked -> isolation"

        unset_view = _curated_titles_visible_to_reader(None)  # dropped GUC -> tagged fail closed
        assert unset_view == {"global entry"}, "unset scope GUC did not fail closed for tagged rows"
    finally:
        with eng.connect() as conn:
            schema.drop_curated_scope_rls(conn)
            schema.drop_reader_rls(conn)
            schema.disable_non_chunk_rls(conn)
            conn.commit()
