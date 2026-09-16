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

from app.platform.config import Settings
from app.platform.db import engine as engine_mod
from app.platform.db import schema

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


def test_apply_reader_rls_leaves_chunk_source_isolation_intact(gateway, settings: Settings) -> None:
    """The reconcile must not touch ``chunk`` — its source-keyed default-deny policy still bites."""
    index_page(gateway, settings, _PAGE, 3)  # chunks land under source_id 'confluence:default'
    try:
        with engine_mod.get_engine().connect() as conn:
            schema.apply_reader_rls(conn)
            conn.commit()

        reader = engine_mod.get_reader_sessionmaker()
        with reader() as s:
            s.execute(text("SET LOCAL app.allowed_sources = 'confluence:other'"))
            mismatched = s.execute(text("SELECT count(*) FROM chunk")).scalar_one()
        with reader() as s:
            s.execute(text("SET LOCAL app.allowed_sources = 'confluence:default'"))
            matched = s.execute(text("SELECT count(*) FROM chunk")).scalar_one()

        assert mismatched == 0, "reconcile weakened chunk source isolation -> cross-source leak"
        assert matched > 0, "chunk policy over-restrictive after reconcile"
    finally:
        with engine_mod.get_engine().connect() as conn:
            schema.drop_reader_rls(conn)
            for table in _READ_TABLES:
                conn.execute(text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))
            conn.commit()


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
