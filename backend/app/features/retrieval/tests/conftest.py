"""Database-test harness wiring for the retrieval feature's ``db``-marked tests.

This directory's DB tests (``test_vector_data_nearest.py``, ``test_vector_data_keyword.py``,
``test_s_reader_role_usage.py``) used to each carry their own copy of the session-scoped engine
bootstrap. That is now the shared ``app.tests.db_harness`` (built once per session via the root
conftest's ``_shared_db_schema``); this conftest only opts db-marked tests into per-test truncation.

The autouse fixture is gated on the ``db`` marker so this directory's DB-free unit tests (fakes, no
network) never request the schema fixture — ``make test-unit`` stays Postgres-free.
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
