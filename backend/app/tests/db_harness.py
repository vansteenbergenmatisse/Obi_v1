"""Shared database-test harness for Obi's ``db``-marked backend suites.

Single source of truth for three things that used to be copy-pasted across five separate harnesses
(``confluence_sync/tests/conftest.py`` plus four retrieval / rag_agent test modules):

1. **The live-host guard (CFG-D).** ``require_local_host`` refuses a non-local ``DATABASE_URL``
   *before* any ``drop_all`` / ``create_all`` / role provisioning runs. It was added after two live
   Supabase incidents (2026-09-16) where an unpinned ``DATABASE_URL`` silently resolved to the live
   pooler; the guard existed in only one of the five harnesses. Consolidating it here means every
   ``db``-marked suite is protected by the same check, with no drift.

2. **The ``*_test`` database bootstrap.** Each old copy derived the test-DB name from the
   *already-mutated* ``DATABASE_URL`` (``get_settings().database_url``), so the second harness to
   run saw ``omniboost_rag_test`` and appended another ``_test`` -> ``omniboost_rag_test_test``,
   and so on for each of the five copies. That cascade — plus five session-scoped fixtures each
   dropping/recreating schema on whatever DB the shared engine singleton pointed at — was the root
   cause of the intermittent cross-test contamination (FLAKE-1). ``test_database_url`` now derives
   the name idempotently and a *single* session-scoped fixture (see ``backend/conftest.py``'s
   ``_shared_db_schema``) builds the schema exactly once per session.

3. **The per-test truncation set.** ``truncate_all`` truncates every mapped table (derived from ORM
   metadata, so a new table is covered automatically) before each test, replacing the three
   different hand-maintained table lists the old copies carried.

The schema shape built here is the superset every consumer needs: ``create_all`` + the non-owner
``rag_reader`` role + the ``chunk`` source and knowledge-scope RLS policies. It deliberately does
**not** apply ``apply_reader_rls`` / ``enable_non_chunk_rls`` — ``test_customer_isolation_backstop``
toggles that non-chunk RLS state itself and relies on the shared harness leaving it off (see that
file's docstring). Owner-role reads bypass RLS (ADR-0013 NO FORCE), so the keyword-only suite is
unaffected by the RLS policies being present.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.engine.url import URL

from app.platform.config import get_settings
from schema import engine as engine_mod
from schema import schema
from schema.base import Base

# Non-owner role the retriever reads as, so RLS is actually exercised (ADR-0004). The writer
# (superuser ``rag``) bypasses RLS; this role does not, which is the point of the isolation tests.
READER_ROLE = "rag_reader"
READER_PASSWORD = "rag_reader_test"

# This harness creates a database, drops/recreates schema, and resets ``rag_reader``'s password on
# whatever host ``DATABASE_URL`` resolves to. Two live incidents (both 2026-09-16) came from an
# unpinned ``DATABASE_URL`` silently resolving to the live Supabase pooler instead of erroring.
# Refuse to touch anything but a local Postgres, before the first connection is even opened.
ALLOWED_TEST_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def require_local_host(url: URL) -> None:
    """Refuse to run the destructive db harness against a non-local host (CFG-D).

    Called before any ``_ensure_database`` / ``drop_all`` / role provisioning, so a misconfigured
    ``DATABASE_URL`` fails loudly instead of dropping schema on a live store.
    """
    if url.host not in ALLOWED_TEST_HOSTS:
        raise RuntimeError(
            f"Refusing to run the database test suite against host {url.host!r}. "
            "DATABASE_URL must point at a local Postgres (localhost/127.0.0.1) before these "
            "tests run — they create a database and reset the rag_reader role's password on "
            "whatever host this resolves to. Run `make test-db` (pins this correctly), or "
            "export DATABASE_URL yourself to the local compose instance before running pytest "
            "directly. Never run a db-marked test with the root .env's DATABASE_URL as-is."
        )


def _ensure_database(url: str) -> None:
    """Create the ``*_test`` database if it does not exist (connecting to ``postgres`` as admin)."""
    u = make_url(url)
    admin_url = u.set(database="postgres")
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": u.database}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{u.database}"'))
    finally:
        admin.dispose()


def test_database_url() -> str:
    """The single shared ``*_test`` database URL, derived *idempotently*.

    Appends ``_test`` only when the current database name does not already end in it, so repeated
    resolution (or a re-entrant fixture) can never cascade ``..._test_test_test`` — the drift that
    caused FLAKE-1.
    """
    base = make_url(get_settings().database_url)
    name = base.database or ""
    if not name.endswith("_test"):
        name = f"{name}_test"
    return base.set(database=name).render_as_string(hide_password=False)


def all_tables() -> list[str]:
    """Every mapped table (from ORM metadata), so a new table is truncated automatically."""
    return sorted(Base.metadata.tables.keys())


def truncate_all() -> None:
    """Truncate every mapped table for deterministic per-test isolation (RESTART IDENTITY)."""
    eng = engine_mod.get_engine()
    with eng.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(all_tables())} RESTART IDENTITY CASCADE"))


def provision_test_database() -> Iterator[None]:
    """Build the shared ``*_test`` schema once per session and wire the owner + reader engines.

    Yields once the database is ready and tears the schema back down at session end. Intended to
    back a single session-scoped fixture (``backend/conftest.py``'s ``_shared_db_schema``); because
    exactly one instance runs per session, the schema is dropped/recreated exactly once, ending the
    order-sensitive multi-fixture rebuild that caused FLAKE-1.
    """
    require_local_host(make_url(get_settings().database_url))
    test_url = test_database_url()
    _ensure_database(test_url)

    os.environ["DATABASE_URL"] = test_url
    get_settings.cache_clear()
    engine_mod.get_engine.cache_clear()
    engine_mod.get_sessionmaker.cache_clear()

    eng = engine_mod.get_engine()
    with eng.begin() as conn:
        schema.drop_all(conn)
        schema.create_all(conn)
        # RLS + the non-owner reader role (ADR-0004), so retrieval is RLS-subject like production.
        schema.ensure_reader_role(conn, role=READER_ROLE, password=READER_PASSWORD)
        schema.apply_chunk_rls(conn)
        # Phase 11.1a / ADR-0014: the customer-scope backstop on chunk (RESTRICTIVE, ANDs with the
        # source policy). Deliberately no apply_reader_rls / enable_non_chunk_rls here — the curated
        # analogue toggles non-chunk RLS state in a dedicated isolated test
        # (test_customer_isolation_backstop), which relies on this shared harness leaving it off.
        schema.apply_chunk_scope_rls(conn)

    # Point the reader engine at the same test DB but as the non-owner rag_reader role.
    reader_url = (
        make_url(test_url)
        .set(username=READER_ROLE, password=READER_PASSWORD)
        .render_as_string(hide_password=False)
    )
    os.environ["DATABASE_READER_URL"] = reader_url
    get_settings.cache_clear()
    engine_mod.get_reader_engine.cache_clear()
    engine_mod.get_reader_sessionmaker.cache_clear()

    yield
    with eng.begin() as conn:
        schema.drop_all(conn)
    engine_mod.get_reader_engine().dispose()
    eng.dispose()
