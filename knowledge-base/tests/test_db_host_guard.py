"""CFG-D-KB-1: the KB db-test live-host guard refuses a non-local DATABASE_URL.

Every db-marked KB test bootstraps a disposable database (``CREATE DATABASE``) and several reset
the ``rag_reader`` role's password on whatever host ``get_kb_settings().database_url`` resolves to.
The autouse guard in ``conftest.py`` (``assert_local_db_host`` → ``require_local_host``) must refuse
a non-local host BEFORE any of that runs.

These tests are deliberately NOT db-marked: they need no Postgres, and proving the guard is a pure
pre-flight check (it builds no engine and opens no connection) is exactly what proves it refuses a
remote host before any ``CREATE DATABASE`` / role reset could occur. ``get_kb_settings()`` reads the
environment fresh on every call, so pointing ``DATABASE_URL`` at a fake remote host via monkeypatch
reproduces the real failure mode (the root .env silently resolving to a live pooler).
"""

from __future__ import annotations

import pytest

# _db_guard is a sibling module resolved at runtime by pytest's prepend import mode (the tests dir
# has no __init__.py); the ignore silences the static-only resolution miss, not a real import error.
from _db_guard import (  # pyright: ignore[reportMissingImports]
    ALLOWED_TEST_HOSTS,
    assert_local_db_host,
    require_local_host,
)
from sqlalchemy.engine import make_url

_REMOTE_URL = "postgresql+psycopg://rag:rag@db.prod.supabase.co:5432/omniboost_rag"
_LOCAL_URL = "postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag"


def test_require_local_host_refuses_a_remote_host() -> None:
    """A non-local host raises RuntimeError, naming the offending host, before any DDL can run."""
    with pytest.raises(RuntimeError, match="db.prod.supabase.co"):
        require_local_host(make_url(_REMOTE_URL))


@pytest.mark.parametrize("host", sorted(ALLOWED_TEST_HOSTS))
def test_require_local_host_allows_local_hosts(host: str) -> None:
    """Each allowed local host is accepted (no exception)."""
    # Set the host via URL.set so IPv6 (``::1``) needs no manual bracketing.
    require_local_host(make_url(_LOCAL_URL).set(host=host))


def test_guard_refuses_when_resolved_settings_point_remote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The resolver used by the autouse fixture refuses a remote DATABASE_URL.

    Mirrors the fixture's exact code path (``assert_local_db_host`` reads settings fresh from the
    env), proving the refusal happens before any harness opens a connection.
    """
    monkeypatch.setenv("DATABASE_URL", _REMOTE_URL)
    with pytest.raises(RuntimeError, match="db.prod.supabase.co"):
        assert_local_db_host()


def test_guard_passes_when_resolved_settings_point_local(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A local DATABASE_URL passes the resolver used by the autouse fixture."""
    monkeypatch.setenv("DATABASE_URL", _LOCAL_URL)
    assert_local_db_host()
