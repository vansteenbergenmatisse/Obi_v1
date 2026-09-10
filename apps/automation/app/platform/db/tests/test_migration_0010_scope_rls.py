"""Phase 11.1a / ADR-0014: 0010 adds the RESTRICTIVE customer-scope policies and is reversible.

Runs the real Alembic chain against a dedicated database. 0010 adds a second, ``AS RESTRICTIVE``
policy to ``chunk`` (``chunk_scope_read``) and to ``curated_knowledge_entry``
(``curated_knowledge_entry_scope_read``), both keyed on the ``app.allowed_knowledge_scopes`` GUC.
RESTRICTIVE is load-bearing: it must AND with the existing permissive source/reader policies (a
permissive policy would OR and weaken isolation), so the test asserts the ``permissive`` flag is
``RESTRICTIVE``. The chain must round-trip (policies gone on downgrade, back on re-upgrade) while
the source spine (``chunk_source_read``) and RLS enable state survive throughout.

Self-contained migration_engine fixture per this repo's one-file-per-migration-test convention
(mirrors test_migration_0009).
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
_BELOW_0010 = "0009_reconcile_non_chunk_rls"
_CHUNK_SCOPE_POLICY = "chunk_scope_read"
_CURATED_SCOPE_POLICY = "curated_knowledge_entry_scope_read"


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


def _policy_row(engine: Engine, table: str, policy: str) -> tuple[str, str] | None:
    """(permissive, cmd) for a policy, or None if absent. permissive: 'PERMISSIVE'/'RESTRICTIVE'."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT permissive, cmd FROM pg_policies WHERE tablename = :t AND policyname = :p"
            ),
            {"t": table, "p": policy},
        ).one_or_none()
    return (row.permissive, row.cmd) if row else None


def _rls_enabled(engine: Engine, table: str) -> bool:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT relrowsecurity FROM pg_class WHERE relname = :t"), {"t": table}
        ).scalar_one()


def test_0010_adds_restrictive_scope_policies(migration_engine: Engine) -> None:
    cfg = _alembic_config()

    command.upgrade(cfg, "head")

    chunk = _policy_row(migration_engine, "chunk", _CHUNK_SCOPE_POLICY)
    curated = _policy_row(migration_engine, "curated_knowledge_entry", _CURATED_SCOPE_POLICY)
    assert chunk == ("RESTRICTIVE", "SELECT"), "chunk scope policy missing or not RESTRICTIVE"
    assert curated == ("RESTRICTIVE", "SELECT"), "curated scope policy missing or not RESTRICTIVE"
    # the source spine is untouched and still present alongside the new restrictive layer
    assert _policy_row(migration_engine, "chunk", "chunk_source_read") is not None
    assert _rls_enabled(migration_engine, "chunk") is True


def test_0010_downgrade_then_upgrade_round_trips(migration_engine: Engine) -> None:
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    assert _policy_row(migration_engine, "chunk", _CHUNK_SCOPE_POLICY) is not None

    command.downgrade(cfg, _BELOW_0010)
    assert _policy_row(migration_engine, "chunk", _CHUNK_SCOPE_POLICY) is None
    assert _policy_row(migration_engine, "curated_knowledge_entry", _CURATED_SCOPE_POLICY) is None
    # the source policy and RLS survive the downgrade — only the scope layer is removed
    assert _policy_row(migration_engine, "chunk", "chunk_source_read") is not None
    assert _rls_enabled(migration_engine, "chunk") is True

    command.upgrade(cfg, "head")
    assert _policy_row(migration_engine, "chunk", _CHUNK_SCOPE_POLICY) == ("RESTRICTIVE", "SELECT")
