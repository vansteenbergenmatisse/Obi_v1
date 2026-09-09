"""Schema lifecycle helpers shared by the Alembic baseline migration and the test harness.

Keeping the extension + ENUM type creation in one place guarantees the migration-built
database and the create_all-built test database are byte-for-byte the same shape.
"""

from __future__ import annotations

from sqlalchemy import Connection, text
from sqlalchemy.dialects.postgresql import ENUM

# import models for side effect: register tables on Base.metadata
from app.platform.db import models  # noqa: F401
from app.platform.db.base import Base
from app.platform.db.enums import PG_ENUMS


def ensure_extensions(conn: Connection) -> None:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def create_enum_types(conn: Connection) -> None:
    for name, enum_cls in PG_ENUMS.items():
        ENUM(*[e.value for e in enum_cls], name=name, create_type=True).create(
            conn, checkfirst=True
        )


def drop_enum_types(conn: Connection) -> None:
    for name in PG_ENUMS:
        conn.execute(text(f'DROP TYPE IF EXISTS "{name}" CASCADE'))


def create_all(conn: Connection) -> None:
    ensure_extensions(conn)
    create_enum_types(conn)
    Base.metadata.create_all(bind=conn)


def drop_all(conn: Connection) -> None:
    Base.metadata.drop_all(bind=conn)
    drop_enum_types(conn)


# --- Row-Level Security + reader role (ADR-0004) ---------------------------------------------
# RLS policies and roles are not expressible in ORM metadata, so this raw DDL is shared by the
# real migration and the test harness (mirroring create_all's "same shape everywhere" contract).

_RLS_POLICY = "chunk_source_read"


def apply_chunk_rls(conn: Connection) -> None:
    """Enable (not FORCE) source-keyed RLS on ``chunk`` with a default-deny policy. Idempotent.

    An unset ``app.allowed_sources`` GUC -> ``string_to_array(NULL, ',')`` -> ``= ANY(NULL)`` is
    never true -> zero rows. RLS is ``ENABLE``d but deliberately **not** ``FORCE``d (ADR-0013): the
    table owner (the writer) is exempt by virtue of ownership alone, while the non-owner
    ``rag_reader`` role stays subject to the policy — which is why retrieval must run as that role.

    ``FORCE`` was dropped so the writer no longer needs SUPERUSER to bypass the default-deny policy:
    managed Postgres (Supabase, RDS) grants no true superuser, so under ``FORCE`` the writer/owner
    would itself be filtered to zero rows and ingestion reads would break. Read-path isolation is
    unchanged — it never depended on ``FORCE``, only on ``rag_reader`` being a non-owner.
    """
    conn.execute(text("ALTER TABLE chunk ENABLE ROW LEVEL SECURITY"))
    # No FORCE: the owner (writer) must read its own rows without SUPERUSER (ADR-0013). Assert
    # NO FORCE so a DB migrated before ADR-0013 is corrected when this idempotent helper reruns.
    conn.execute(text("ALTER TABLE chunk NO FORCE ROW LEVEL SECURITY"))
    conn.execute(text(f"DROP POLICY IF EXISTS {_RLS_POLICY} ON chunk"))
    conn.execute(
        text(
            f"CREATE POLICY {_RLS_POLICY} ON chunk FOR SELECT "
            "USING (source_id = ANY(string_to_array("
            "current_setting('app.allowed_sources', true), ',')))"
        )
    )


def drop_chunk_rls(conn: Connection) -> None:
    """Reverse ``apply_chunk_rls`` (for migration downgrade). Idempotent."""
    conn.execute(text(f"DROP POLICY IF EXISTS {_RLS_POLICY} ON chunk"))
    conn.execute(text("ALTER TABLE chunk NO FORCE ROW LEVEL SECURITY"))
    conn.execute(text("ALTER TABLE chunk DISABLE ROW LEVEL SECURITY"))


def ensure_reader_role(conn: Connection, *, role: str, password: str) -> None:
    """Create a non-owner, non-superuser login role granted read-only access. Idempotent.

    ``role``/``password`` are trusted deployment constants (never user input). CREATE ROLE cannot
    bind identifiers or passwords, so the role name is validated as a plain identifier and the
    password is single-quote-escaped before interpolation.
    """
    if not role.replace("_", "").isalnum():
        raise ValueError(f"unsafe reader role name: {role!r}")
    exists = conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}).scalar()
    esc = password.replace("'", "''")
    verb = "CREATE" if not exists else "ALTER"
    # CREATE when absent; ALTER to (re)assert the password when the cluster-global role lingers
    # from a prior run — keeps the login deterministic without dropping the role.
    conn.execute(
        text(
            f"{verb} ROLE {role} LOGIN PASSWORD '{esc}' "
            "NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS"
        )
    )
    conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
    conn.execute(text(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}"))
    conn.execute(
        text(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {role}")
    )
