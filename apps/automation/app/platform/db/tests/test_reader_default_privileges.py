"""Panel r3-reader / substep 0.5.3: default privileges cover a table created after provisioning.

``ensure_reader_role`` (schema.py) grants ``rag_reader`` two things: an explicit ``GRANT SELECT ON
ALL TABLES`` for tables that exist at provisioning time, and ``ALTER DEFAULT PRIVILEGES ... GRANT
SELECT ON TABLES`` for tables that do not exist yet. The explicit grant is proven implicitly by
every other DB test (they all read through ``rag_reader``), but nothing proves the *default*
privileges clause end to end: that a table created strictly AFTER the role already exists is
readable by ``rag_reader`` with no additional explicit ``GRANT`` ever issued for it.

Runs against a dedicated, disposable database (mirroring test_migration_0009's pattern) so the
new probe table and the timing of "role first, table second" are unambiguous and do not disturb
the shared local test database other suites use.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

from app.platform.config import get_settings
from app.platform.db import schema

pytestmark = pytest.mark.db  # substep 0.5.1: real local Postgres

_READER_ROLE = "rag_reader"
_READER_PASSWORD = "rag_reader_test"
_PROBE_TABLE = "reader_default_priv_probe"


def _ensure_database(admin_url: str, dbname: str) -> None:
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": dbname}
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    finally:
        admin.dispose()


def _drop_database(admin_url: str, dbname: str) -> None:
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :n AND pid <> pg_backend_pid()"
                ),
                {"n": dbname},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{dbname}"'))
    finally:
        admin.dispose()


@pytest.fixture
def owner_engine() -> Iterator[Engine]:
    base = make_url(get_settings().database_url)
    dbname = f"{base.database}_reader_defaults_test"
    db_url_str = base.set(database=dbname).render_as_string(hide_password=False)
    admin_url = base.set(database="postgres").render_as_string(hide_password=False)

    _ensure_database(admin_url, dbname)
    eng = create_engine(db_url_str)
    try:
        yield eng
    finally:
        eng.dispose()
        _drop_database(admin_url, dbname)


def test_r3_reader_default_privileges_cover_a_table_created_after_role_provisioning(
    owner_engine: Engine,
) -> None:
    """panel r3-reader · substep 0.5.3
    A table created in `public` strictly after ensure_reader_role has already provisioned
    rag_reader is selectable by rag_reader through the ALTER DEFAULT PRIVILEGES grant alone,
    with no explicit GRANT ever issued for that specific table."""
    with owner_engine.begin() as conn:
        # Role first: this is the ONLY grant statement that runs. The explicit
        # "GRANT SELECT ON ALL TABLES" inside it has nothing to grant yet (fresh db, no tables).
        schema.ensure_reader_role(conn, role=_READER_ROLE, password=_READER_PASSWORD)
        # Table second, strictly after the role (and its default-privileges rule) already exist.
        conn.execute(text(f"CREATE TABLE {_PROBE_TABLE} (id integer PRIMARY KEY)"))
        conn.execute(text(f"INSERT INTO {_PROBE_TABLE} (id) VALUES (1)"))

    reader_url = (
        make_url(owner_engine.url)
        .set(username=_READER_ROLE, password=_READER_PASSWORD)
        .render_as_string(hide_password=False)
    )
    reader_engine = create_engine(reader_url)
    try:
        with reader_engine.connect() as conn:
            row_count = conn.execute(text(f"SELECT count(*) FROM {_PROBE_TABLE}")).scalar_one()
    finally:
        reader_engine.dispose()

    assert row_count == 1
