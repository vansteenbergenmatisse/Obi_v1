"""Live-host guard for the knowledge-base ``db``-marked test suite (CFG-D-KB-1).

Every ``db``-marked KB test bootstraps a disposable database: it issues ``CREATE DATABASE`` and,
for several suites, resets the ``rag_reader`` role's password on whatever host
``get_kb_settings().database_url`` resolves to. If that URL silently resolves to a live host
(for example the Supabase pooler, via the root ``.env``), those DDL / role operations would run
against production — the same failure mode as the two live incidents (2026-09-16) that the
backend's guard was added for.

This module mirrors ``backend/app/tests/db_harness.py``'s ``require_local_host`` *by copy, not by
import*: ``knowledge-base/`` imports nothing from ``backend/`` (ADR-0018, enforced by
``make boundaries``), so the KB tree owns its own guard helper. ``conftest.py`` wires it as an
autouse, ``db``-gated fixture that runs before any harness opens its first admin connection;
DB-free KB unit tests never touch it (they carry no ``db`` marker).
"""

from __future__ import annotations

from sqlalchemy.engine import make_url
from sqlalchemy.engine.url import URL

from schema.settings import get_kb_settings

# Only a local Postgres may be dropped/recreated and have its rag_reader password reset by a test.
ALLOWED_TEST_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def require_local_host(url: URL) -> None:
    """Refuse to run a destructive KB db harness against a non-local host (CFG-D-KB-1).

    Pure pre-flight check: it constructs no engine and opens no connection, so raising here
    guarantees no ``CREATE DATABASE`` / ``drop_all`` / role-password reset can have run yet.
    """
    if url.host not in ALLOWED_TEST_HOSTS:
        raise RuntimeError(
            f"Refusing to run the knowledge-base database test suite against host {url.host!r}. "
            "DATABASE_URL must point at a local Postgres (localhost/127.0.0.1) before these "
            "tests run — each one creates a database and several reset the rag_reader role's "
            "password on whatever host this resolves to. Point DATABASE_URL at the local "
            "pgvector compose (make up) before running pytest directly. Never run a db-marked "
            "test with the root .env's DATABASE_URL as-is."
        )


def assert_local_db_host() -> None:
    """Resolve the KB DB settings and refuse a non-local host.

    ``get_kb_settings()`` reads the environment fresh on every call (it is deliberately uncached),
    so this reflects the URL the harness fixtures will actually connect to.
    """
    require_local_host(make_url(get_kb_settings().database_url))
