"""panel mi-applies · substep 8.2.2: 0015 adds the applicability stamp columns; reversible.

Runs the real Alembic chain against a dedicated database. 0015 adds a nullable JSONB
``applicability`` column to ``chunk`` and ``page_source`` — the validated "Applies to"
record stamped during sync (NULL = no record = the documented label-only default). The
test asserts the columns exist at head (jsonb, nullable), the downgrade to 0014 removes
them cleanly, and a re-upgrade restores them — the migration round-trip the substep's
Must-be-true names. No RLS policy changes ride this migration (applicability never
grants access; the scope/source policies are untouched).

Self-contained migration_engine fixture per this repo's one-file-per-migration-test
convention (mirrors test_migration_0014).
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

pytestmark = pytest.mark.db  # real local Postgres, Alembic chain

_BELOW_0015 = "0014_chunk_scope_fail_closed"
_TABLES = ("chunk", "page_source")


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
    dbname = f"{base.database}_migration_0015_test"
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


def _column(engine: Engine, table: str, column: str) -> tuple[str, str] | None:
    """(data_type, is_nullable) for a column, or None if it does not exist."""
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT data_type, is_nullable FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).one_or_none()
    return (row.data_type, row.is_nullable) if row else None


def test_in2_applies_0015_adds_nullable_jsonb_applicability_at_head(
    migration_engine: Engine,
) -> None:
    """panel mi-applies · substep 8.2.2
    At head, chunk and page_source carry a nullable jsonb applicability column."""
    command.upgrade(_alembic_config(), "head")
    for table in _TABLES:
        col = _column(migration_engine, table, "applicability")
        assert col is not None, f"{table}.applicability missing at head"
        assert col == ("jsonb", "YES"), f"{table}.applicability is {col}, want nullable jsonb"


def test_in2_applies_0015_downgrade_round_trips_cleanly(migration_engine: Engine) -> None:
    """panel mi-applies · substep 8.2.2
    The migration downgrades cleanly: 0015 -> 0014 removes both columns, a re-upgrade
    restores them — reversible, as every schema change must be."""
    cfg = _alembic_config()
    command.upgrade(cfg, "head")
    for table in _TABLES:
        assert _column(migration_engine, table, "applicability") is not None

    command.downgrade(cfg, _BELOW_0015)
    for table in _TABLES:
        assert _column(migration_engine, table, "applicability") is None, (
            f"downgrade left {table}.applicability behind"
        )

    command.upgrade(cfg, "head")
    for table in _TABLES:
        assert _column(migration_engine, table, "applicability") == ("jsonb", "YES")
