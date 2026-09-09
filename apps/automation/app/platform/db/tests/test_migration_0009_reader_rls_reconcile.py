"""Phase 13.1: 0009 adds reader-scoped RLS policies (keeps RLS on) and is reversible.

Runs the real Alembic chain against a dedicated database. 0009 keeps RLS enabled on the non-chunk
tables (so Supabase's anon/authenticated stay default-denied) and adds a ``TO rag_reader`` SELECT
policy to the reader's read set. The policy is only created when the rag_reader role exists, so the
test ensures the (cluster-global) role is present, then asserts the policy appears on upgrade,
disappears on downgrade, and comes back — while chunk keeps RLS throughout.

The migration_engine fixture mirrors test_migration_0007's (kept self-contained per this repo's
one-file-per-migration-test convention).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

from alembic import command
from app.platform.config import get_settings
from app.platform.db import engine as engine_mod

_AUTOMATION_ROOT = Path(__file__).resolve().parents[4]
_BELOW_0009 = "0008_drop_force_rls"
_ENSURE_READER = (
    "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rag_reader') THEN "
    "CREATE ROLE rag_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS; END IF; END $$"
)


def _ensure_database(admin_url: str, dbname: str) -> None:
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": dbname}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    finally:
        admin.dispose()


def _drop_database(admin_url: str, dbname: str) -> None:
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :n AND pid <> pg_backend_pid()"
                ),
                {"n": dbname},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{dbname}"'))
    finally:
        admin.dispose()


def _alembic_config() -> Config:
    cfg = Config(str(_AUTOMATION_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_AUTOMATION_ROOT / "alembic"))
    return cfg


@pytest.fixture
def migration_engine() -> Iterator[Engine]:
    base = make_url(get_settings().database_url)
    dbname = f"{base.database}_migration_test"
    test_url = base.set(database=dbname)
    admin_url = base.set(database="postgres").render_as_string(hide_password=False)
    test_url_str = test_url.render_as_string(hide_password=False)

    _ensure_database(admin_url, dbname)

    prior_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url_str
    get_settings.cache_clear()

    eng = create_engine(test_url_str)
    with eng.connect() as conn:
        conn.execute(text(_ENSURE_READER))  # cluster-global role so 0009 creates the reader policy
        conn.commit()
    try:
        yield eng
    finally:
        eng.dispose()
        if prior_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prior_database_url
        get_settings.cache_clear()
        engine_mod.get_engine.cache_clear()
        _drop_database(admin_url, dbname)


def _rls_enabled(engine: Engine, table: str) -> bool:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT relrowsecurity FROM pg_class WHERE relname = :t"), {"t": table}
        ).scalar_one()


def _policy_exists(engine: Engine, table: str, policy: str) -> bool:
    with engine.connect() as conn:
        return (
            conn.execute(
                text("SELECT 1 FROM pg_policies WHERE tablename = :t AND policyname = :p"),
                {"t": table, "p": policy},
            ).scalar()
            is not None
        )


def test_0009_adds_reader_policy_and_keeps_rls_on(migration_engine: Engine) -> None:
    cfg = _alembic_config()

    command.upgrade(cfg, "head")

    assert _rls_enabled(migration_engine, "page_source") is True
    assert _rls_enabled(migration_engine, "curated_knowledge_entry") is True
    assert _policy_exists(migration_engine, "page_source", "page_source_reader_read")
    assert _policy_exists(
        migration_engine, "curated_knowledge_entry", "curated_knowledge_entry_reader_read"
    )
    assert _rls_enabled(migration_engine, "chunk") is True  # isolation spine untouched


def test_0009_downgrade_then_upgrade_round_trips(migration_engine: Engine) -> None:
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    assert _policy_exists(migration_engine, "page_source", "page_source_reader_read")

    command.downgrade(cfg, _BELOW_0009)
    assert not _policy_exists(migration_engine, "page_source", "page_source_reader_read")
    assert _rls_enabled(migration_engine, "page_source") is False  # disable_non_chunk_rls ran
    assert _rls_enabled(migration_engine, "chunk") is True

    command.upgrade(cfg, "head")
    assert _policy_exists(migration_engine, "page_source", "page_source_reader_read")
    assert _rls_enabled(migration_engine, "page_source") is True
