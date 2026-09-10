"""NEXT FIXES #1 (P0) / Phase 13.2: ``rag_reader`` must be able to resolve pgvector types.

On Supabase pgvector is installed into an ``extensions`` schema (not ``public``), and the reader
role is granted no ``USAGE`` there and has ``extensions`` off its ``search_path``. Every dense query
(``embedding::halfvec(dim)``) then fails as ``rag_reader`` with ``type "halfvec" does not exist`` /
``permission denied for schema extensions`` — so live semantic retrieval, which MUST run as
the non-owner reader (ADR-0004), is broken. ``schema.ensure_reader_role`` must therefore grant it
``USAGE`` on the ``extensions`` schema and add it to the role ``search_path`` whenever that schema
exists (a local/RDS install puts pgvector in ``public``, where the reader is already covered).

The live GRANT on Supabase's supabase-owned ``extensions`` schema is applied by the operator (the
owner role is permission-gated off it); these tests exercise the code path against a local install
where the owner can grant, and a rolled-back transaction keeps the shared session DB clean.
"""

from __future__ import annotations

from sqlalchemy import text

from app.platform.db import engine as engine_mod
from app.platform.db import schema

_READER_ROLE = "rag_reader"


def test_reader_can_run_dense_halfvec_query() -> None:
    """Regression guard: the reader can resolve/cast ``halfvec`` (the production dense-query path).

    If the reader ever loses access to the schema holding pgvector's types, this fails the same way
    live retrieval does — ``type "halfvec" does not exist`` — instead of silently at query time.
    """
    reader = engine_mod.get_reader_sessionmaker()
    with reader() as s:
        casted = s.execute(text("SELECT CAST('[1,2,3]' AS halfvec(3))")).scalar_one()
    assert casted is not None


def test_ensure_reader_role_grants_extensions_usage_when_schema_exists() -> None:
    """When an ``extensions`` schema exists, the reader gets USAGE on it + it joins search_path."""
    eng = engine_mod.get_engine()
    with eng.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS extensions"))
            schema.ensure_reader_role(conn, role=_READER_ROLE, password="rag_reader_test")

            usage = conn.execute(
                text("SELECT has_schema_privilege(:r, 'extensions', 'USAGE')"),
                {"r": _READER_ROLE},
            ).scalar_one()
            rolconfig = conn.execute(
                text("SELECT rolconfig FROM pg_roles WHERE rolname = :r"),
                {"r": _READER_ROLE},
            ).scalar_one()

            assert usage is True, "reader lacks USAGE on extensions -> dense query fails as reader"
            assert rolconfig is not None and any(
                c.startswith("search_path=") and "extensions" in c for c in rolconfig
            ), "extensions not on the reader role search_path -> halfvec unresolved as reader"
        finally:
            trans.rollback()


def test_ensure_reader_role_no_extensions_schema_is_a_noop_for_extensions() -> None:
    """A local/RDS install (pgvector in ``public``, no ``extensions`` schema) must not error.

    ensure_reader_role stays idempotent and grants no phantom ``extensions`` access. This also
    exercises the re-provision (role-already-exists) path, which on managed Postgres must be a bare
    password reset with no role-attribute clauses (NEXT FIXES #2).
    """
    eng = engine_mod.get_engine()
    with eng.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text("DROP SCHEMA IF EXISTS extensions CASCADE"))
            schema.ensure_reader_role(conn, role=_READER_ROLE, password="rag_reader_test")
            schema.ensure_reader_role(conn, role=_READER_ROLE, password="rag_reader_test")

            ext_exists = conn.execute(
                text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'extensions'")
            ).scalar()
            assert ext_exists is None, "test setup drop failed"
        finally:
            trans.rollback()
