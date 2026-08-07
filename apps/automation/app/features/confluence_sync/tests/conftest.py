"""Database-backed test harness for the confluence_sync feature.

Scoped to this package so the (DB-free) evaluation tests are unaffected. Points the whole app
engine at a dedicated ``*_test`` database, builds the schema once per session with the same
``schema.create_all`` the migration uses, and truncates every table between tests for isolation.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.platform.clients import FixtureConfluenceGateway
from app.platform.config import Settings, get_settings
from app.platform.db import engine as engine_mod
from app.platform.db import schema

_TABLES = [
    "chunk",
    "document_version",
    "document",
    "page_source",
    "job",
    "event_ledger",
    "reconciliation_run",
]


def _ensure_database(url: str) -> None:
    u = make_url(url)
    admin_url = u.set(database="postgres")
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": u.database}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{u.database}"'))
    finally:
        admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def _configure_test_engine() -> Iterator[None]:
    base = make_url(get_settings().database_url)
    test_url = base.set(database=f"{base.database}_test").render_as_string(hide_password=False)
    _ensure_database(test_url)

    os.environ["DATABASE_URL"] = test_url
    get_settings.cache_clear()
    engine_mod.get_engine.cache_clear()
    engine_mod.get_sessionmaker.cache_clear()

    eng = engine_mod.get_engine()
    with eng.begin() as conn:
        schema.drop_all(conn)
        schema.create_all(conn)
    yield
    with eng.begin() as conn:
        schema.drop_all(conn)
    eng.dispose()


@pytest.fixture(autouse=True)
def _truncate(_configure_test_engine: None) -> Iterator[None]:
    eng = engine_mod.get_engine()
    with eng.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(_TABLES)} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def session() -> Iterator[Session]:
    """A session for direct DB seeding/asserting. Tests commit explicitly when needed."""
    s = engine_mod.get_sessionmaker()()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def gateway() -> FixtureConfluenceGateway:
    return FixtureConfluenceGateway()


@pytest.fixture
def settings() -> Settings:
    # Hermetic: strip webhook credentials that may be present in the developer's
    # real .env (loaded by get_settings()), so tests exercise the unconfigured
    # path deterministically regardless of the local environment. model_copy
    # preserves the *_test database URL and env wired by _configure_test_engine.
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
