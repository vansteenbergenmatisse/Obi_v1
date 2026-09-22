"""Database-test harness wiring for the rag_agent feature's ``db``-marked tests.

``test_s_reader_curated_fetch.py`` used to carry its own copy of the session-scoped engine
bootstrap; that is now the shared ``app.tests.db_harness`` (built once per session via the root
conftest's ``_shared_db_schema``). This conftest only opts db-marked tests into per-test truncation.

The autouse fixture is gated on the ``db`` marker so this directory's DB-free unit tests never
request the schema fixture — ``make test-unit`` stays Postgres-free.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def _db_isolation(request: pytest.FixtureRequest) -> Iterator[None]:
    """Truncate every table before each ``db``-marked test; a no-op for DB-free tests."""
    if request.node.get_closest_marker("db") is None:
        yield
        return
    request.getfixturevalue("_shared_db_schema")
    from app.tests.db_harness import truncate_all

    truncate_all()
    yield
