"""Phase 13.1: let ``rag_reader`` read its non-``chunk`` tables WITHOUT exposing them to ``anon``.

The retrieval reader (rag_reader, non-BYPASSRLS) reads page_source / page_restriction (the page ACL)
and curated_knowledge_entry (curated layer). On Supabase those tables had RLS enabled with no
policy, so the reader was default-denied and read zero rows — the ACL failed open and the curated
layer went dark. But disabling RLS is unsafe: Supabase's PostgREST roles anon/authenticated hold
blanket GRANT SELECT, so RLS is the only thing keeping the corpus off the public REST endpoint.
Disabling it would expose every row to unauthenticated callers.

``schema.apply_reader_rls`` keeps RLS enabled and adds a ``FOR SELECT TO rag_reader`` policy, so the
reader is let back in while any other role (here a purpose-built anon-like role that mirrors
Supabase's anon: a non-superuser, non-BYPASSRLS role holding GRANT SELECT) stays default-denied. The
critical assertion is the last one: after the fix the anon-like role STILL reads zero rows.

RLS state survives ``TRUNCATE``, so each test resets ``_READER_READ_TABLES`` to RLS-off in a
``finally`` to keep the shared session DB clean.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.platform.config import Settings
from schema import engine as engine_mod
from schema import schema

from ._helpers import index_page

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest

_PAGE = 1001  # space 100, unrestricted (the fixture page the other RLS tests use)
_ANON = "anon_like_test"  # mirrors Supabase's public `anon`: SELECT grant, no BYPASSRLS
_READ_TABLES = ("page_source", "page_restriction", "curated_knowledge_entry")

_ENSURE_ANON = (
    "DO $$ BEGIN "
    f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_ANON}') THEN "
    f"CREATE ROLE {_ANON} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS; END IF; END $$"
)


def _count_as_anon(conn, table: str) -> int:
    """Read ``table`` while impersonating the anon-like role (SET ROLE drops the superuser bit)."""
    conn.execute(text(f"SET ROLE {_ANON}"))
    try:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
    finally:
        conn.execute(text("RESET ROLE"))


def test_reader_freed_but_anon_stays_denied(gateway, settings: Settings) -> None:
    """apply_reader_rls lets rag_reader read page_source; the anon-like role stays denied."""
    index_page(gateway, settings, _PAGE, 3)  # commits >=1 page_source row

    eng = engine_mod.get_engine()
    reader = engine_mod.get_reader_sessionmaker()
    try:
        # Reproduce the live Supabase posture: RLS enabled (no policy) + anon holds SELECT.
        with eng.connect() as conn:
            conn.execute(text(_ENSURE_ANON))
            conn.execute(text(f"GRANT SELECT ON page_source TO {_ANON}"))
            conn.execute(text("ALTER TABLE page_source ENABLE ROW LEVEL SECURITY"))
            conn.commit()

        with reader() as s:
            reader_before = s.execute(text("SELECT count(*) FROM page_source")).scalar_one()
        with eng.connect() as conn:
            anon_before = _count_as_anon(conn, "page_source")
        assert reader_before == 0, "precondition: RLS/no-policy should lock the reader out"
        assert anon_before == 0, "precondition: RLS/no-policy should lock the anon-like role out"

        # The Phase 13.1 fix: reader-scoped policy, RLS stays enabled.
        with eng.connect() as conn:
            schema.apply_reader_rls(conn)
            conn.commit()

        with reader() as s:
            reader_after = s.execute(text("SELECT count(*) FROM page_source")).scalar_one()
        with eng.connect() as conn:
            anon_after = _count_as_anon(conn, "page_source")
        assert reader_after > 0, (
            "reader still locked out after apply_reader_rls -> page ACL fail-open"
        )
        assert anon_after == 0, (
            "anon-like role can read page_source after the fix -> PUBLIC REST DATA LEAK"
        )
    finally:
        with eng.connect() as conn:
            schema.drop_reader_rls(conn)
            for table in _READ_TABLES:
                conn.execute(text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
            conn.execute(text(f"REVOKE SELECT ON page_source FROM {_ANON}"))
            conn.commit()


def test_s_anon_denied_by_rls_despite_grant_independent_of_reader_policy(
    gateway, settings: Settings
) -> None:
    """panel s-anon · substep 0.5 regression
    Duplicates test_reader_freed_but_anon_stays_denied's two anon-side assertions under this
    panel's own name (established precedent: every check should be provable by a test literally
    named for its own panel). The anon-like role holds GRANT SELECT on page_source throughout, yet
    reads zero rows both before AND after rag_reader gets its own FOR SELECT TO rag_reader policy
    -- proving RLS-with-no-matching-policy denies it despite the grant, and that the denial does
    not depend on whatever policy exists (or doesn't) for rag_reader.
    """
    index_page(gateway, settings, _PAGE, 3)  # commits >=1 page_source row

    eng = engine_mod.get_engine()
    try:
        # Reproduce the live Supabase posture: RLS enabled (no policy) + anon holds SELECT.
        with eng.connect() as conn:
            conn.execute(text(_ENSURE_ANON))
            conn.execute(text(f"GRANT SELECT ON page_source TO {_ANON}"))
            conn.execute(text("ALTER TABLE page_source ENABLE ROW LEVEL SECURITY"))
            conn.commit()

        with eng.connect() as conn:
            anon_before = _count_as_anon(conn, "page_source")
        assert anon_before == 0, (
            "anon-like role read rows despite GRANT SELECT + no matching policy -> denial failed"
        )

        # rag_reader now gets its own policy; anon's denial must not depend on this either way.
        with eng.connect() as conn:
            schema.apply_reader_rls(conn)
            conn.commit()

        with eng.connect() as conn:
            anon_after = _count_as_anon(conn, "page_source")
        assert anon_after == 0, (
            "anon-like role can read page_source once rag_reader has its own policy -> "
            "denial was not independent of rag_reader's policy state"
        )
    finally:
        with eng.connect() as conn:
            schema.drop_reader_rls(conn)
            for table in _READ_TABLES:
                conn.execute(text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
            conn.execute(text(f"REVOKE SELECT ON page_source FROM {_ANON}"))
            conn.commit()


def test_apply_reader_rls_leaves_chunk_source_isolation_intact(gateway, settings: Settings) -> None:
    """The reconcile must not touch ``chunk`` — its source-keyed default-deny policy still bites."""
    index_page(gateway, settings, _PAGE, 3)  # chunks land under source_id 'confluence:default'
    try:
        with engine_mod.get_engine().connect() as conn:
            schema.apply_reader_rls(conn)
            conn.commit()

        # Source-axis assertion only: opt out of the knowledge-scope axis with '*' so the
        # now-always-tagged chunks (2.2.4 membership gate) are judged on source alone.
        reader = engine_mod.get_reader_sessionmaker()
        with reader() as s:
            s.execute(text("SET LOCAL app.allowed_sources = 'confluence:other'"))
            s.execute(text("SET LOCAL app.allowed_knowledge_scopes = '*'"))
            mismatched = s.execute(text("SELECT count(*) FROM chunk")).scalar_one()
        with reader() as s:
            s.execute(text("SET LOCAL app.allowed_sources = 'confluence:default'"))
            s.execute(text("SET LOCAL app.allowed_knowledge_scopes = '*'"))
            matched = s.execute(text("SELECT count(*) FROM chunk")).scalar_one()

        assert mismatched == 0, "reconcile weakened chunk source isolation -> cross-source leak"
        assert matched > 0, "chunk policy over-restrictive after reconcile"
    finally:
        with engine_mod.get_engine().connect() as conn:
            schema.drop_reader_rls(conn)
            for table in _READ_TABLES:
                conn.execute(text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
            conn.commit()


def _seed_one_row_per_reader_table(gateway, settings: Settings) -> None:
    """One committed row in every ``_READER_READ_TABLES`` member, so each visibility assertion
    below counts a real row rather than passing vacuously on an empty table."""
    index_page(gateway, settings, _PAGE, 3)  # page_source row (+ chunk rows)
    with engine_mod.get_sessionmaker()() as s:
        s.execute(
            text("INSERT INTO page_restriction (page_id, principal) VALUES (:p, 'group:eng')"),
            {"p": _PAGE},
        )
        s.execute(
            text(
                "INSERT INTO curated_knowledge_entry (tags, title, body, is_active) "
                "VALUES (:tags, 'g11 entry', 'g11 body', true)"
            ),
            {"tags": []},
        )
        s.commit()


def test_sec_reader_read_table_list_cannot_silently_shrink() -> None:
    """panel s-anon · substep 4.2 (coverage gap G11)
    The production reader-read set must keep covering every table retrieval reads via the reader
    session (the page ACL pair + the curated layer). The parameterized test below derives its
    cases from the production list at collection time, so WITHOUT this pin a table dropped from
    ``_READER_READ_TABLES`` would silently drop its proof instead of failing."""
    assert {"page_source", "page_restriction", "curated_knowledge_entry"} <= set(
        schema._READER_READ_TABLES
    )


@pytest.mark.parametrize("table", schema._READER_READ_TABLES)
def test_sec_every_reader_read_table_readable_by_reader_denied_to_anon(
    gateway, settings: Settings, table: str
) -> None:
    """panel s-anon · substep 4.2 (coverage gap G11)
    EVERY production ``_READER_READ_TABLES`` member (page_source, page_restriction,
    curated_knowledge_entry) — not just the page_source the earlier tests hardcode — is readable
    by rag_reader once ``apply_reader_rls`` runs, while the anon-like role (GRANT SELECT, no
    BYPASSRLS, mirroring Supabase's public REST role) reads zero rows before AND after.
    Parameterized over the production list itself so a newly added reader table is covered
    automatically; each table carries a seeded row so visibility is a real assertion."""
    _seed_one_row_per_reader_table(gateway, settings)

    eng = engine_mod.get_engine()
    with eng.connect() as conn:  # owner bypasses RLS: proves the row is really there
        seeded = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
    assert seeded > 0, f"vacuous test: no seeded row in {table}"

    reader = engine_mod.get_reader_sessionmaker()
    try:
        # The live Supabase posture: RLS enabled (no policy yet) + anon holds SELECT.
        with eng.connect() as conn:
            conn.execute(text(_ENSURE_ANON))
            conn.execute(text(f"GRANT SELECT ON {table} TO {_ANON}"))
            conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
            conn.commit()

        with reader() as s:
            reader_before = s.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
        with eng.connect() as conn:
            anon_before = _count_as_anon(conn, table)
        assert reader_before == 0, f"precondition: RLS/no-policy should deny the reader {table}"
        assert anon_before == 0, f"precondition: RLS/no-policy should lock anon out of {table}"

        with eng.connect() as conn:
            schema.apply_reader_rls(conn)
            conn.commit()

        with reader() as s:
            reader_after = s.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
        with eng.connect() as conn:
            anon_after = _count_as_anon(conn, table)
        assert reader_after == seeded, f"rag_reader cannot read {table} after apply_reader_rls"
        assert anon_after == 0, f"anon-like role can read {table} -> PUBLIC REST DATA LEAK"
    finally:
        with eng.connect() as conn:
            schema.drop_reader_rls(conn)
            for t in _READ_TABLES:
                conn.execute(text(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY"))
            conn.execute(text(f"REVOKE SELECT ON {table} FROM {_ANON}"))
            conn.commit()


def test_sec_reader_set_role_to_owner_is_denied(gateway, settings: Settings) -> None:
    """panel s-reader · substep 4.2 (coverage gap G12)
    Privilege escalation via ``SET ROLE``: as rag_reader (NOSUPERUSER, no membership in the
    owner role), ``SET ROLE <owner>`` is denied by Postgres with a permission error — the reader
    can never become the RLS-exempt writer. Afterwards the same session still works as
    rag_reader, so the denial is a clean error, not a broken connection."""
    owner_role = engine_mod.get_engine().url.username  # the writer role the harness provisions
    assert owner_role and owner_role != "rag_reader"

    reader = engine_mod.get_reader_sessionmaker()
    with reader() as s:
        with pytest.raises(ProgrammingError, match="permission denied"):
            s.execute(text(f"SET ROLE {owner_role}"))
        s.rollback()  # the failed SET ROLE aborted the transaction; the session survives

        assert s.execute(text("SELECT current_user")).scalar_one() == "rag_reader"


def test_apply_reader_rls_skips_policy_when_role_absent(gateway, settings: Settings) -> None:
    """A fresh deploy runs alembic before the reader role exists: RLS on, but no policy yet."""
    index_page(gateway, settings, _PAGE, 3)
    try:
        with engine_mod.get_engine().connect() as conn:
            schema.apply_reader_rls(conn, role="no_such_reader_role")
            rls_on = conn.execute(
                text("SELECT relrowsecurity FROM pg_class WHERE relname = 'page_source'")
            ).scalar_one()
            policy = conn.execute(
                text(
                    "SELECT 1 FROM pg_policies WHERE tablename = 'page_source' "
                    "AND policyname = 'page_source_reader_read'"
                )
            ).scalar()
            conn.commit()
        assert rls_on is True, (
            "RLS must be enabled even when the reader role is absent (anon safety)"
        )
        assert policy is None, "no reader policy should be created for a non-existent role"
    finally:
        with engine_mod.get_engine().connect() as conn:
            for table in _READ_TABLES:
                conn.execute(text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
            conn.commit()
