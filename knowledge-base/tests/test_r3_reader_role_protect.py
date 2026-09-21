"""Protect panel r3-reader / substep p0-s0_5-reg-retrieval-stage-3.

r3-reader's own checks are: the role's attributes (``LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
NOBYPASSRLS``), its grants (``SELECT`` on the read tables that exist at provisioning time, plus
default privileges for tables created afterward). The default-privileges half is already proven end
to end by ``test_reader_default_privileges.py``; nothing before this file asserted the role's actual
``pg_roles`` attributes, or that the explicit ``GRANT SELECT ON ALL TABLES`` covers a table that
already existed *before* ``ensure_reader_role`` ran (as opposed to one created after).

This is a "protect" test: ``ensure_reader_role`` (schema.py) already works today. Nothing here
changes production code — only locks the current, correct behavior in with a regression test, so a
future change to that function trips a red test instead of silently drifting from the panel.

Runs against a dedicated, disposable database (mirroring ``test_reader_default_privileges.py``'s
pattern) so it never disturbs the shared local test database other suites use.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

from schema import schema
from schema.settings import get_kb_settings as get_settings

pytestmark = pytest.mark.db  # substep 0.5.1: real local Postgres

_READER_ROLE = "rag_reader"
_READER_PASSWORD = "rag_reader_test"
_PREEXISTING_TABLE = "reader_preexisting_probe"


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
    dbname = f"{base.database}_reader_protect_test"
    db_url_str = base.set(database=dbname).render_as_string(hide_password=False)
    admin_url = base.set(database="postgres").render_as_string(hide_password=False)

    _ensure_database(admin_url, dbname)
    eng = create_engine(db_url_str)
    try:
        yield eng
    finally:
        eng.dispose()
        _drop_database(admin_url, dbname)


def test_r3_reader_role_attributes_are_login_nosuperuser_nocreatedb_nocreaterole_nobypassrls(
    owner_engine: Engine,
) -> None:
    """panel r3-reader · substep p0-s0_5-reg-retrieval-stage-3
    ensure_reader_role creates rag_reader with exactly the panel's attributes: LOGIN,
    NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOBYPASSRLS."""
    with owner_engine.begin() as conn:
        schema.ensure_reader_role(conn, role=_READER_ROLE, password=_READER_PASSWORD)
        row = conn.execute(
            text(
                "SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls "
                "FROM pg_roles WHERE rolname = :r"
            ),
            {"r": _READER_ROLE},
        ).one()

    assert row.rolcanlogin is True, "rag_reader must be able to LOGIN"
    assert row.rolsuper is False, "rag_reader must be NOSUPERUSER"
    assert row.rolcreatedb is False, "rag_reader must be NOCREATEDB"
    assert row.rolcreaterole is False, "rag_reader must be NOCREATEROLE"
    assert row.rolbypassrls is False, "rag_reader must be NOBYPASSRLS"


def test_r3_reader_select_grant_covers_a_table_that_existed_before_role_provisioning(
    owner_engine: Engine,
) -> None:
    """panel r3-reader · substep p0-s0_5-reg-retrieval-stage-3
    A table created BEFORE ensure_reader_role provisions rag_reader is selectable by rag_reader
    through the explicit `GRANT SELECT ON ALL TABLES` clause (the read-tables grant, distinct
    from the default-privileges clause covering tables created afterward)."""
    with owner_engine.begin() as conn:
        # Table first: exists at provisioning time, so only the explicit "ALL TABLES" grant --
        # not the default-privileges clause -- can cover it.
        conn.execute(text(f"CREATE TABLE {_PREEXISTING_TABLE} (id integer PRIMARY KEY)"))
        conn.execute(text(f"INSERT INTO {_PREEXISTING_TABLE} (id) VALUES (1)"))
        schema.ensure_reader_role(conn, role=_READER_ROLE, password=_READER_PASSWORD)

    reader_url = (
        make_url(owner_engine.url)
        .set(username=_READER_ROLE, password=_READER_PASSWORD)
        .render_as_string(hide_password=False)
    )
    reader_engine = create_engine(reader_url)
    try:
        with reader_engine.connect() as conn:
            row_count = conn.execute(
                text(f"SELECT count(*) FROM {_PREEXISTING_TABLE}")
            ).scalar_one()
    finally:
        reader_engine.dispose()

    assert row_count == 1
