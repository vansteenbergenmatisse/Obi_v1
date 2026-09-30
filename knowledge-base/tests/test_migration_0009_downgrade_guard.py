"""0009 downgrade guard: refuse to disable non-chunk RLS on a Supabase host (CLAUDE.md rule #1).

0009's downgrade disables ROW LEVEL SECURITY on the non-chunk tables; on Supabase that re-exposes
every row to the public ``anon``/``authenticated`` REST roles. ``_refuse_supabase_downgrade`` reads
the host off the live bind and raises before any DDL can run.

These tests are deliberately NOT ``db``-marked: they build a fake bind (no engine, no connection),
so proving the guard raises on a Supabase host and passes on localhost needs no Postgres — the same
pure pre-flight style as ``test_db_host_guard.py``. The migration module name starts with a digit,
so it is loaded by path via importlib rather than a normal import.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

_MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "0009_reconcile_non_chunk_rls.py"
)


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_mig_0009_guard", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_bind(host: str) -> SimpleNamespace:
    """Stand-in for ``op.get_bind()``: the guard reads only ``.engine.url.host``."""
    url = make_url("postgresql+psycopg://u:p@placeholder:5432/db").set(host=host)
    return SimpleNamespace(engine=SimpleNamespace(url=url))


def test_downgrade_guard_blocks_supabase_host() -> None:
    """A Supabase host raises RuntimeError with the block message, before any DDL runs."""
    mig = _load_migration()
    with pytest.raises(RuntimeError, match="never downgrade 0009 on Supabase"):
        mig._refuse_supabase_downgrade(_fake_bind("db.vtpbwkbbkfukfmytlqns.supabase.co"))


def test_downgrade_guard_allows_localhost() -> None:
    """localhost does not raise — local downgrades must still work."""
    mig = _load_migration()
    mig._refuse_supabase_downgrade(_fake_bind("localhost"))
