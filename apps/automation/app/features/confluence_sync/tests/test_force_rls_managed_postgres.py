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

from sqlalchemy import text

from app.platform.config import Settings
from app.platform.db import engine as engine_mod

from ._helpers import index_page

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
