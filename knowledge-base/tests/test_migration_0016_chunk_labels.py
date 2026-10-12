"""Option A Stage 3 / substep 9.1.2: migration 0016 adds the raw-labels column; reversible.

Runs the real Alembic chain against a dedicated database. 0016 adds ``labels text[]`` to ``chunk``
and ``page_source``, a partial GIN ``ix_chunk_labels_gin`` on ``chunk`` ``WHERE is_active``, and the
RESTRICTIVE ``chunk_labels_read`` policy (keyed on the new ``app.allowed_labels`` GUC, a no-op until
9.4.1 wires it). The test reads catalog metadata and asserts:

* at head, both ``labels`` columns, the GIN index and the RESTRICTIVE policy exist;
* downgrade to 0015 drops all of them cleanly (reversible — never-bend rule 11);
* re-upgrade restores them.

Throughout, the chunk source + scope policies (locks 1-2) and the chunk RLS enable state survive:
0016 only adds, it never weakens isolation. Self-contained migration_engine fixture per this repo's
one-file-per-migration-test convention (mirrors test_migration_0014).
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
_BELOW_0016 = "0015_applicability_stamp"
_LABELS_POLICY = "chunk_labels_read"
_LABELS_INDEX = "ix_chunk_labels_gin"


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
    dbname = f"{base.database}_migration_0016_test"
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


def _column_exists(engine: Engine, table: str, column: str) -> bool:
    with engine.connect() as conn:
        return bool(
            conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = :t AND column_name = :c"
                ),
                {"t": table, "c": column},
            ).scalar()
        )


def _index_exists(engine: Engine, index: str) -> bool:
    with engine.connect() as conn:
        return bool(
            conn.execute(
                text("SELECT 1 FROM pg_indexes WHERE indexname = :i"), {"i": index}
            ).scalar()
        )


def _policy(engine: Engine, table: str, policy: str) -> tuple[str, str, str] | None:
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


def test_0016_adds_labels_column_index_and_policy(migration_engine: Engine) -> None:
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    assert _column_exists(migration_engine, "chunk", "labels"), "chunk.labels missing at head"
    assert _column_exists(migration_engine, "page_source", "labels"), "page_source.labels missing"
    assert _index_exists(migration_engine, _LABELS_INDEX), "GIN ix_chunk_labels_gin missing"

    policy = _policy(migration_engine, "chunk", _LABELS_POLICY)
    assert policy is not None, "chunk_labels_read policy missing at head"
    permissive, cmd, qual = policy
    assert (permissive, cmd) == ("RESTRICTIVE", "SELECT"), "labels policy not RESTRICTIVE"
    assert "&&" in qual, f"labels overlap predicate missing: {qual}"

    # locks 1-2 and RLS enable state survive — 0016 only adds
    assert _policy(migration_engine, "chunk", "chunk_source_read") is not None
    assert _policy(migration_engine, "chunk", "chunk_scope_read") is not None
    assert _rls_enabled(migration_engine, "chunk") is True


def test_0016_downgrade_drops_everything_then_upgrade_restores(migration_engine: Engine) -> None:
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    assert _column_exists(migration_engine, "chunk", "labels")

    command.downgrade(cfg, _BELOW_0016)
    assert not _column_exists(migration_engine, "chunk", "labels"), "downgrade left chunk.labels"
    assert not _column_exists(migration_engine, "page_source", "labels"), "downgrade left ps.labels"
    assert not _index_exists(migration_engine, _LABELS_INDEX), "downgrade left the GIN index"
    assert _policy(migration_engine, "chunk", _LABELS_POLICY) is None, "downgrade left the policy"
    # the scope/source spine and RLS survive the downgrade (0016 never touched them)
    assert _policy(migration_engine, "chunk", "chunk_scope_read") is not None
    assert _policy(migration_engine, "chunk", "chunk_source_read") is not None
    assert _rls_enabled(migration_engine, "chunk") is True

    command.upgrade(cfg, "head")
    assert _column_exists(migration_engine, "chunk", "labels")
    assert _policy(migration_engine, "chunk", _LABELS_POLICY) is not None
