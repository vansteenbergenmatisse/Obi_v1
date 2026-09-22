"""Database-backed test harness for the confluence_sync feature.

The destructive bootstrap (live-host guard, ``*_test`` database, schema + RLS + reader role) now
lives in the shared ``app.tests.db_harness`` module and runs once per session via the root
conftest's ``_shared_db_schema`` fixture; this file only adds the per-test truncation and the
feature-specific ``gateway`` / ``settings`` fixtures. The owner ``session`` fixture is provided by
the root conftest. Scoped to this package so the (DB-free) evaluation tests are unaffected.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.platform.clients import FixtureConfluenceGateway
from app.platform.config import Settings, get_settings


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


@pytest.fixture
def gateway() -> FixtureConfluenceGateway:
    return FixtureConfluenceGateway()


@pytest.fixture
def settings() -> Settings:
    # Hermetic: strip webhook credentials that may be present in the developer's
    # real .env (loaded by get_settings()), so tests exercise the unconfigured
    # path deterministically regardless of the local environment. model_copy
    # preserves the *_test database URL and env wired by the shared harness.
    return get_settings().model_copy(
        update={
            "confluence_webhook_secret": "",
            "confluence_service_account_id": "",
        }
    )


@pytest.fixture
def webhook_settings() -> Settings:
    """Settings wired for the webhook: a signing secret and a known service-account id."""
    return get_settings().model_copy(
        update={
            "confluence_webhook_secret": "test-webhook-secret",
            "confluence_service_account_id": "acct-service-bot",
        }
    )
