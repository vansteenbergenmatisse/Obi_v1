"""PLAN 11.1c (ADR-0014): 0011 must be a true, reversible ``head -> 0010 -> head`` migration that
adds ``query_trace.subject_hash``.

Runs the real Alembic chain against a dedicated database (same harness discipline as
test_migration_0007), so the raw DDL is exercised the way a deploy would. Reversibility is proven
by round-tripping: upgrade to head, confirm the column exists, downgrade one step to 0010, confirm
it's gone, upgrade again, confirm it's back."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url

from alembic import command
from app.platform.config import get_settings
from app.platform.db import engine as engine_mod

_AUTOMATION_ROOT = Path(__file__).resolve().parents[4]

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
    cfg = Config(str(_AUTOMATION_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_AUTOMATION_ROOT / "alembic"))
    return cfg


@pytest.fixture
def migration_engine() -> Iterator[Engine]:
    base = make_url(get_settings().database_url)
    dbname = f"{base.database}_migration_0011_test"
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


def _columns(engine: Engine) -> set[str]:
    return {c["name"] for c in inspect(engine).get_columns("query_trace")}


def test_0011_adds_subject_hash_and_round_trips(migration_engine: Engine) -> None:
    cfg = _alembic_config()

    command.upgrade(cfg, "head")
    assert "subject_hash" in _columns(migration_engine)

    command.downgrade(cfg, "0010_customer_scope_rls")
    assert "subject_hash" not in _columns(migration_engine)

    command.upgrade(cfg, "head")
    assert "subject_hash" in _columns(migration_engine)
