"""CFG-D: the shared db harness must refuse a non-local ``DATABASE_URL`` before it drops schema.

These are unit tests (no ``db`` marker, no Postgres): they prove the live-host guard fires — and
fires *first*, before ``_ensure_database`` / ``drop_all`` / role provisioning could ever run against
a remote store. This is the check that was missing from four of the five old, duplicated harnesses
(the 2026-09-16 live-Supabase incidents); it now lives once, in ``app.tests.db_harness``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.engine import make_url

from app.tests import db_harness

_REMOTE_URL = "postgresql+psycopg://user:pw@db.abcdefgh.supabase.co:5432/postgres"
_LOCAL_URL = "postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag"


def test_require_local_host_rejects_a_remote_host() -> None:
    with pytest.raises(RuntimeError, match="local Postgres"):
        db_harness.require_local_host(make_url(_REMOTE_URL))


@pytest.mark.parametrize("url", [_LOCAL_URL, _LOCAL_URL.replace("localhost", "127.0.0.1")])
def test_require_local_host_allows_a_local_host(url: str) -> None:
    # Must not raise for the allowed local hosts.
    db_harness.require_local_host(make_url(url))


def test_provision_refuses_remote_url_before_touching_the_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard fires before any destructive step, so a misconfigured remote ``DATABASE_URL`` can
    never reach ``_ensure_database`` (CREATE DATABASE) or ``drop_all`` on a live store."""
    monkeypatch.setattr(
        db_harness, "get_settings", lambda: SimpleNamespace(database_url=_REMOTE_URL)
    )

    called: list[str] = []
    monkeypatch.setattr(
        db_harness, "_ensure_database", lambda url: called.append("_ensure_database")
    )
    monkeypatch.setattr(db_harness.schema, "drop_all", lambda conn: called.append("drop_all"))

    gen = db_harness.provision_test_database()
    with pytest.raises(RuntimeError, match="local Postgres"):
        next(gen)  # start the generator: runs the guard, then would build the schema

    assert called == [], "guard did not fail-closed BEFORE the destructive steps"
