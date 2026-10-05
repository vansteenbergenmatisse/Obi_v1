"""0010/0014 downgrade guards: refuse to loosen scope RLS on a Supabase host (X1, 2026-10-05).

0010's downgrade drops the knowledge-scope policies outright; 0014's restores the
empty-tags-means-public floor. Either one run against the live store reopens a cross-tenant /
cross-scope leak, so both now carry the same enforced host guard 0009 pioneered
(``test_migration_0009_downgrade_guard.py``) — accepted as open decision X1 from the 4.2
coverage audit.

Deliberately NOT ``db``-marked: a fake bind (no engine, no connection) proves the guard raises on
a Supabase host and passes on localhost without Postgres. Migration module names start with a
digit, so they load by path via importlib.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

_VERSIONS = Path(__file__).resolve().parents[1] / "migrations" / "versions"
_MIGRATIONS = {
    "0010": _VERSIONS / "0010_customer_scope_rls.py",
    "0014": _VERSIONS / "0014_chunk_scope_fail_closed.py",
}


def _load_migration(key: str) -> ModuleType:
    path = _MIGRATIONS[key]
    spec = importlib.util.spec_from_file_location(f"_mig_{key}_guard", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_bind(host: str) -> SimpleNamespace:
    """Stand-in for ``op.get_bind()``: the guard reads only ``.engine.url.host``."""
    url = make_url("postgresql+psycopg://u:p@placeholder:5432/db").set(host=host)
    return SimpleNamespace(engine=SimpleNamespace(url=url))


@pytest.mark.parametrize("key", ["0010", "0014"])
def test_downgrade_guard_blocks_supabase_host(key: str) -> None:
    """A Supabase host raises RuntimeError with the block message, before any DDL runs."""
    mig = _load_migration(key)
    with pytest.raises(RuntimeError, match=f"never downgrade {key} on Supabase"):
        mig._refuse_supabase_downgrade(_fake_bind("db.vtpbwkbbkfukfmytlqns.supabase.co"))


@pytest.mark.parametrize("key", ["0010", "0014"])
def test_downgrade_guard_allows_localhost(key: str) -> None:
    """localhost does not raise — local downgrades (and the round-trip tests) must still work."""
    mig = _load_migration(key)
    mig._refuse_supabase_downgrade(_fake_bind("localhost"))
