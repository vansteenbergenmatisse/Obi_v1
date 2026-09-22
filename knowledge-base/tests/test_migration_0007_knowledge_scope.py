"""PLAN 10.3: 0007_knowledge_scope must be a true, reversible ``head -> -1 -> head`` migration.

Runs the real Alembic chain (not ``schema.create_all``) against a dedicated database so the
migration's raw DDL is exercised directly, the way it would be in a real deploy. Reversibility is
asserted by round-tripping: upgrade to head, confirm the new shape, downgrade one step, confirm the
pre-migration shape is fully restored (not just "doesn't error"), upgrade again, confirm the new
shape is back byte-for-byte.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url

from schema import engine as engine_mod
from schema.settings import get_kb_settings as get_settings

# knowledge-base/ is two levels up from knowledge-base/tests/ (1.1.1-fix: this suite
# now lives under knowledge-base/tests/, not backend/tests/schema/).
_KB_ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.db  # substep 0.5.1: real local Postgres, Alembic chain


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
    dbname = f"{base.database}_migration_0007_test"
    test_url = base.set(database=dbname)
    admin_url = base.set(database="postgres").render_as_string(hide_password=False)
    test_url_str = test_url.render_as_string(hide_password=False)

    _ensure_database(admin_url, dbname)

    prior_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url_str
    # get_kb_settings() reads env fresh (uncached), so there is no settings cache to clear here;
    # env.py's get_settings() sees the new DATABASE_URL directly (1.1.1-fix: KB-native settings).

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


def _has_table(engine: Engine, table: str) -> bool:
    return inspect(engine).has_table(table)


def _column_names(engine: Engine, table: str) -> set[str]:
    return {c["name"] for c in inspect(engine).get_columns(table)}


def _index_def(engine: Engine, index_name: str) -> str | None:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = :n"), {"n": index_name}
        ).scalar_one_or_none()


def test_0007_upgrade_creates_the_new_shape(migration_engine: Engine) -> None:
    cfg = _alembic_config()

    command.upgrade(cfg, "head")

    assert _has_table(migration_engine, "curated_knowledge_entry")
    assert _column_names(migration_engine, "curated_knowledge_entry") == {
        "id",
        "tags",
        "title",
        "body",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert "allowed_knowledge_scopes" in _column_names(migration_engine, "query_trace")
    index_def = _index_def(migration_engine, "ix_chunk_tags_gin")
    assert index_def is not None
    assert "USING gin" in index_def
    assert "is_active" in index_def


def test_0007_downgrade_then_upgrade_round_trips_cleanly(migration_engine: Engine) -> None:
    cfg = _alembic_config()
    command.upgrade(cfg, "head")

    # Downgrade to the revision *below* 0007 by explicit id (not a relative "-1", which breaks the
    # moment any later migration is added on top of 0007 — as 0008 now is).
    command.downgrade(cfg, "0006_dedupe_source_type_check")

    assert not _has_table(migration_engine, "curated_knowledge_entry")
    assert "allowed_knowledge_scopes" not in _column_names(migration_engine, "query_trace")
    assert _index_def(migration_engine, "ix_chunk_tags_gin") is None

    command.upgrade(cfg, "head")

    assert _has_table(migration_engine, "curated_knowledge_entry")
    assert "allowed_knowledge_scopes" in _column_names(migration_engine, "query_trace")
    index_def = _index_def(migration_engine, "ix_chunk_tags_gin")
    assert index_def is not None
    assert "USING gin" in index_def
