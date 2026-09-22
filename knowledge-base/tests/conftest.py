"""Knowledge-base test fixtures.

Holds the CFG-D-KB-1 live-host guard: an autouse, ``db``-gated fixture that refuses a non-local
``DATABASE_URL`` before any ``db``-marked harness performs a destructive op (``CREATE DATABASE``,
``drop_all`` / ``create_all``, or a ``rag_reader`` password reset). The check lives in the sibling
``_db_guard`` module (importable by bare name — the tests directory has no ``__init__.py``, so
pytest's prepend import mode puts it on ``sys.path``); see that module for why the KB tree carries
its own copy instead of importing the backend's guard (ADR-0018 one-way boundary).
"""

from __future__ import annotations

import pytest

# _db_guard is a sibling module resolved at runtime by pytest's prepend import mode (the tests dir
# has no __init__.py); the ignore silences the static-only resolution miss, not a real import error.
from _db_guard import assert_local_db_host  # pyright: ignore[reportMissingImports]


@pytest.fixture(autouse=True)
def _guard_local_db_host(request: pytest.FixtureRequest) -> None:
    """Refuse a non-local DATABASE_URL before any db-marked harness runs.

    Function-scoped and autouse, so it is set up before the test's own (function-scoped) harness
    fixtures — ``owner_engine`` / ``migration_engine`` / ``indexed_engine`` — and therefore before
    their first ``CREATE DATABASE`` or role-password reset. Gated on the ``db`` marker so DB-free
    KB unit tests are completely unaffected.
    """
    if request.node.get_closest_marker("db") is None:
        return
    assert_local_db_host()
