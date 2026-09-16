"""Phase 11.1a — the customer-isolation DB backstop (ADR-0014), read-path side.

The mews/opera/toast/general boundary was enforced *only* by an app-layer ``tags && :scopes``
predicate gated behind ``enable_knowledge_scope_filtering`` — which **failed open** (flag off, or a
single dropped predicate, returned every customer's rows to everyone). Source isolation already
fails *closed* via ADR-0004 RLS; the customer axis did not.

This adds a second, **RESTRICTIVE** RLS policy on ``chunk`` (``chunk_scope_read``) keyed on a new
per-transaction GUC ``app.allowed_knowledge_scopes``, mirroring ``app.allowed_sources``. Being
RESTRICTIVE it **ANDs** with the source policy (a second *permissive* policy would OR, weakening
isolation). Semantics:

* GUC set to a scope list -> only chunks whose ``tags`` overlap it are visible.
* GUC unset (a dropped call / bug) -> ``current_setting`` is NULL -> policy denies (fail closed).
* GUC set to the explicit sentinel ``'*'`` -> unrestricted (the internal/eval path opts out on
  purpose; the public ``/chat`` path always resolves a real scope list, never ``'*'``).

These tests read ``chunk`` directly as the non-owner ``rag_reader`` (RLS-subject; the owner is
exempt by ADR-0013 ``NO FORCE``) with **no app-layer predicate at all**, so they prove the DB
enforces the boundary on its own. Mirrors ``test_force_rls_managed_postgres.py``'s direct reads.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.platform.config import Settings
from app.platform.db import engine as engine_mod
from app.platform.db import schema
from app.platform.db.engine import get_reader_sessionmaker

from ._helpers import index_page

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest

_MEWS_PAGE = 1001  # space 100, unrestricted
_OPERA_PAGE = 2001  # space 200, unrestricted
_READER_ROLE = "rag_reader"


def _set_chunk_tags(page_id: int, tags: list[str]) -> None:
    from app.platform.db.engine import get_sessionmaker

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


def test_scope_rls_untagged_chunk_is_global_visible_under_any_scope(
    gateway, settings: Settings
) -> None:
    """An UNTAGGED chunk is global (``cardinality(tags) = 0``): it stays visible under any real
    scope list, so a corpus not using knowledge-scope tagging keeps working and the always-on base
    is never hidden. Only a *tagged* chunk is isolated (proven by the cross-customer test above).
    This is the security floor; the stricter ADR-0011 Decision-1 app predicate may drop it when the
    scope-filtering flag is on — a product choice layered ON TOP, not the RLS boundary."""
    index_page(gateway, settings, _MEWS_PAGE, 3)
    _set_chunk_tags(_MEWS_PAGE, [])  # no scope tag at all -> global

    reader = get_reader_sessionmaker()
    with reader() as s:
        s.execute(text("SET LOCAL app.allowed_sources = 'confluence:default'"))
        s.execute(
            text("SELECT set_config('app.allowed_knowledge_scopes', 'obi-operacloud-test', true)")
        )
        under_foreign_scope = _count_chunks(s, _MEWS_PAGE)

    assert under_foreign_scope > 0, "untagged (global) chunk hidden -> untagged corpus would break"


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
    """The curated analogue of the chunk backstop (ADR-0014): as ``rag_reader``, a curated entry
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
