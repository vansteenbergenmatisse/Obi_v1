"""sync-rules step 4 / D3: 0014 drops the empty-tags floor from ``chunk_scope_read``; reversible.

Runs the real Alembic chain against a dedicated database. 0014 rewrites the RESTRICTIVE
``chunk_scope_read`` policy to pure ``tags``-overlap, dropping the ``OR cardinality(tags) = 0``
floor that made an untagged chunk global (a cross-scope leak on last-tag removal). The test
reads the policy's ``USING`` expression from ``pg_policies.qual`` and asserts:

* at head, ``qual`` has no ``cardinality`` clause (floor gone) and the policy stays RESTRICTIVE;
* downgrade to 0013 restores the with-floor policy (``cardinality`` back in ``qual``) — reversible;
* re-upgrade drops the floor again.

Throughout, the source spine (``chunk_source_read``) and chunk RLS enable state survive, and the
curated policy keeps its own floor (0014 touches only ``chunk``). Self-contained migration_engine
fixture per this repo's one-file-per-migration-test convention (mirrors test_migration_0010).
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

from schema import engine as engine_mod
from schema.settings import get_kb_settings as get_settings

_KB_ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.db  # substep 0.5.1: real local Postgres, Alembic chain
_BELOW_0014 = "0013_reindex_progress"
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
    cfg = Config(str(_KB_ROOT / "migrations" / "alembic.ini"))
    cfg.set_main_option("script_location", str(_KB_ROOT / "migrations"))
    return cfg


@pytest.fixture
def migration_engine() -> Iterator[Engine]:
    base = make_url(get_settings().database_url)
    dbname = f"{base.database}_migration_0014_test"
    test_url = base.set(database=dbname)
    admin_url = base.set(database="postgres").render_as_string(hide_password=False)
    test_url_str = test_url.render_as_string(hide_password=False)

    _ensure_database(admin_url, dbname)

    prior_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url_str

    eng = create_engine(test_url_str)
    try:
        yield eng
    finally:
        eng.dispose()
        if prior_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = prior_database_url
        engine_mod.get_engine.cache_clear()
        _drop_database(admin_url, dbname)


def _policy(engine: Engine, table: str, policy: str) -> tuple[str, str, str] | None:
    """(permissive, cmd, qual) for a policy, or None. qual is the USING expression text."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT permissive, cmd, qual FROM pg_policies "
                "WHERE tablename = :t AND policyname = :p"
            ),
            {"t": table, "p": policy},
        ).one_or_none()
    return (row.permissive, row.cmd, row.qual) if row else None


def _rls_enabled(engine: Engine, table: str) -> bool:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT relrowsecurity FROM pg_class WHERE relname = :t"), {"t": table}
        ).scalar_one()


def test_0014_drops_the_empty_tags_floor(migration_engine: Engine) -> None:
    cfg = _alembic_config()

    command.upgrade(cfg, "0014_chunk_scope_fail_closed")  # ADR-routing-labels-sole-content-axis: pin below 0018

    chunk = _policy(migration_engine, "chunk", _CHUNK_SCOPE_POLICY)
    assert chunk is not None, "chunk scope policy missing at head"
    permissive, cmd, qual = chunk
    assert (permissive, cmd) == ("RESTRICTIVE", "SELECT"), "chunk scope policy not RESTRICTIVE"
    assert "cardinality" not in qual, f"empty-tags floor still present at head: {qual}"
    assert "&&" in qual, f"overlap predicate missing from chunk scope policy: {qual}"
    # curated keeps its own floor (0014 touches only chunk)
    curated = _policy(migration_engine, "curated_knowledge_entry", _CURATED_SCOPE_POLICY)
    assert curated is not None and "cardinality" in curated[2], "curated floor wrongly removed"
    # source spine + RLS survive
    assert _policy(migration_engine, "chunk", "chunk_source_read") is not None
    assert _rls_enabled(migration_engine, "chunk") is True


def test_0014_downgrade_restores_floor_then_upgrade_drops_it(migration_engine: Engine) -> None:
    cfg = _alembic_config()
    command.upgrade(cfg, "0014_chunk_scope_fail_closed")  # ADR-routing-labels-sole-content-axis: pin below 0018
    assert "cardinality" not in _policy(migration_engine, "chunk", _CHUNK_SCOPE_POLICY)[2]

    command.downgrade(cfg, _BELOW_0014)
    reverted = _policy(migration_engine, "chunk", _CHUNK_SCOPE_POLICY)
    assert reverted is not None, "downgrade dropped the policy entirely instead of restoring it"
    assert reverted[:2] == ("RESTRICTIVE", "SELECT"), "restored policy not RESTRICTIVE"
    assert "cardinality" in reverted[2], "downgrade did not restore the empty-tags floor"
    # source policy and RLS survive the downgrade
    assert _policy(migration_engine, "chunk", "chunk_source_read") is not None
    assert _rls_enabled(migration_engine, "chunk") is True

    command.upgrade(cfg, "0014_chunk_scope_fail_closed")  # ADR-routing-labels-sole-content-axis: pin below 0018
    assert "cardinality" not in _policy(migration_engine, "chunk", _CHUNK_SCOPE_POLICY)[2]
