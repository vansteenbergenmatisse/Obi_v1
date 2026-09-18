"""ADR-0013 / Phase 6 step 1: the writer must read its own rows WITHOUT being a superuser.

Today ``chunk`` is under ``FORCE ROW LEVEL SECURITY`` and the writer escapes the default-deny
policy *only by being a superuser* (local ``rag`` is one — FORCE makes even the table owner subject,
so ownership alone would not be enough). Managed Postgres (Supabase, RDS) grants no true superuser,
so on cutover the writer would be filtered to zero rows and ingestion/reconcile reads would break.

The fix (ADR-0013): drop ``FORCE`` but keep ``ENABLE`` — a non-superuser *owner* then bypasses RLS,
while the non-owner ``rag_reader`` stays policy-bound and isolation on the read path is unchanged.

These tests reproduce the managed-Postgres condition on the real ``chunk`` table by handing its
ownership to a purpose-built NON-superuser role and reading as that role (``SET ROLE`` drops the
superuser bit), then restore ownership. The first test is the fix's acceptance criterion; the second
proves the drop did not weaken read-path isolation for the non-owner reader.

Lock note: the ownership swap takes an ACCESS EXCLUSIVE lock on ``chunk``. We seed first and hold
that lock only within a single connection/transaction that touches nothing else, so no other
connection is ever blocked on it.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from app.platform.config import Settings
from app.platform.db import engine as engine_mod

from ._helpers import index_page

pytestmark = (
    pytest.mark.db
)  # substep 0.5.1: real local Postgres via this dir's session-scoped conftest

_PAGE = 1001  # space 100, unrestricted (same fixture page the other RLS tests use)
_MANAGED_WRITER = "mp_writer_test"  # a non-superuser owner, mimicking Supabase/RDS' `postgres`

_ENSURE_ROLE = (
    "DO $$ BEGIN "
    f"IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{_MANAGED_WRITER}') THEN "
    f"CREATE ROLE {_MANAGED_WRITER} NOLOGIN "
    "NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS; END IF; END $$"
)


def test_non_superuser_owner_reads_own_rows(gateway, settings: Settings) -> None:
    """The managed-Postgres writer (non-superuser OWNER) must see its rows with no GUC set."""
    index_page(gateway, settings, _PAGE, 3)  # seed + commit BEFORE we take the exclusive lock

    eng = engine_mod.get_engine()
    with eng.connect() as conn:
        original_owner = conn.execute(
            text("SELECT tableowner FROM pg_tables WHERE tablename = 'chunk'")
        ).scalar_one()
        try:
            conn.execute(text(_ENSURE_ROLE))
            conn.execute(text(f"ALTER TABLE chunk OWNER TO {_MANAGED_WRITER}"))
            conn.execute(text(f"SET ROLE {_MANAGED_WRITER}"))
            current = conn.execute(text("SELECT current_user")).scalar_one()
            rows = conn.execute(text("SELECT count(*) FROM chunk")).scalar_one()
            conn.execute(text("RESET ROLE"))
        finally:
            conn.execute(text("RESET ROLE"))
            conn.execute(text(f'ALTER TABLE chunk OWNER TO "{original_owner}"'))
            conn.commit()

    assert current == _MANAGED_WRITER  # guard: SET ROLE really dropped the superuser bit
    # With FORCE present this is 0 (owner filtered by the default-deny policy) -> ingestion breaks.
    assert rows > 0, "non-superuser owner filtered by RLS -> managed-Postgres writer would break"


def test_s_writer_owner_reads_and_writes_without_rls_policy_match(
    gateway, settings: Settings
) -> None:
    """panel s-writer · substep 0.5 regression
    Duplicates test_non_superuser_owner_reads_own_rows's read proof under this panel's own name
    (established precedent: every check should be provable by a test literally named for its own
    panel) and extends it to writes -- the managed-Postgres writer (non-superuser OWNER) can also
    UPDATE its own rows with no scope/source GUC set, not just SELECT them. Neither is filtered by
    a matching RLS policy; both come from ownership exemption alone (FORCE is off).
    """
    index_page(gateway, settings, _PAGE, 3)  # seed + commit BEFORE we take the exclusive lock

    eng = engine_mod.get_engine()
    with eng.connect() as conn:
        original_owner = conn.execute(
            text("SELECT tableowner FROM pg_tables WHERE tablename = 'chunk'")
        ).scalar_one()
        try:
            conn.execute(text(_ENSURE_ROLE))
            conn.execute(text(f"ALTER TABLE chunk OWNER TO {_MANAGED_WRITER}"))
            conn.execute(text(f"SET ROLE {_MANAGED_WRITER}"))
            read_count = conn.execute(text("SELECT count(*) FROM chunk")).scalar_one()
            updated = conn.execute(
                text("UPDATE chunk SET display_content = display_content WHERE page_id = :p"),
                {"p": _PAGE},
            ).rowcount
            conn.execute(text("RESET ROLE"))
        finally:
            conn.execute(text("RESET ROLE"))
            conn.execute(text(f'ALTER TABLE chunk OWNER TO "{original_owner}"'))
            conn.commit()

    assert read_count > 0, "owner blocked from reading its own rows with no GUC set"
    assert updated > 0, "owner blocked from writing its own rows with no GUC set"


def test_non_owner_reader_still_isolated(gateway, settings: Settings) -> None:
    """Dropping FORCE must not open the non-owner reader: it stays bound by app.allowed_sources."""
    index_page(gateway, settings, _PAGE, 3)  # chunks land under source_id 'confluence:default'

    reader = engine_mod.get_reader_sessionmaker()
    with reader() as s:
        s.execute(text("SET LOCAL app.allowed_sources = 'confluence:other'"))
        mismatched = s.execute(text("SELECT count(*) FROM chunk")).scalar_one()
    with reader() as s:
        s.execute(text("SET LOCAL app.allowed_sources = 'confluence:default'"))
        matched = s.execute(text("SELECT count(*) FROM chunk")).scalar_one()

    assert mismatched == 0, "reader saw rows for a source it was not scoped to -> isolation leak"
    assert matched > 0, "reader could not see rows for its own scope -> policy over-restrictive"


def test_s_writer_chunk_rls_enabled_but_not_forced() -> None:
    """panel s-writer · substep 0.5 regression
    chunk carries the exact catalog state ADR-0013 requires: RLS ENABLEd (relrowsecurity) so
    non-owner roles are policy-bound, but NOT FORCEd (relforcerowsecurity) so the table owner
    stays exempt by ownership alone -- the mechanic managed Postgres (no true superuser) depends
    on. This is the deterministic equivalent of coverage-map.md's staging-only pg_class check.
    """
    eng = engine_mod.get_engine()
    with eng.connect() as conn:
        row_security, force_row_security = conn.execute(
            text(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE oid = 'chunk'::regclass"
            )
        ).one()

    assert row_security is True, (
        "chunk must have RLS enabled -- non-owner roles must be policy-bound"
    )
    assert force_row_security is False, (
        "chunk must NOT have FORCE ROW LEVEL SECURITY -- FORCE would filter the owner too, "
        "breaking the managed-Postgres writer (ADR-0013)"
    )


def test_s_writer_owner_role_has_no_superuser_or_bypassrls() -> None:
    """panel s-writer · substep 0.5 regression
    The managed-Postgres writer role (mp_writer_test, standing in for Supabase's non-superuser
    `postgres`) holds neither SUPERUSER nor BYPASSRLS in pg_roles. Combined with the sibling test
    proving that role still reads its own rows, this shows the read access comes from ownership
    alone -- never from an elevated privilege that would not exist on managed Postgres.
    """
    eng = engine_mod.get_engine()
    with eng.begin() as conn:
        conn.execute(text(_ENSURE_ROLE))
        rolsuper, rolbypassrls = conn.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"),
            {"r": _MANAGED_WRITER},
        ).one()

    assert rolsuper is False, "managed-Postgres writer must not be a superuser"
    assert rolbypassrls is False, "managed-Postgres writer must not hold BYPASSRLS"
