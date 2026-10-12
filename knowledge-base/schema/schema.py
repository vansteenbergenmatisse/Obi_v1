"""Schema lifecycle helpers shared by the Alembic baseline migration and the test harness.

Keeping the extension + ENUM type creation in one place guarantees the migration-built
database and the create_all-built test database are byte-for-byte the same shape.
"""

from __future__ import annotations

from sqlalchemy import Connection, text
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.exc import ProgrammingError

# import models for side effect: register tables on Base.metadata
from schema import models  # noqa: F401
from schema.base import Base
from schema.enums import PG_ENUMS


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


# --- Phase 11.1a: customer/knowledge-scope isolation backstop (ADR-0014) ----------------------
# A second axis on top of the source policy above. The mews/opera/toast/general boundary used to be
# an app-layer ``tags && :scopes`` predicate gated by a fail-OPEN feature flag; this makes the DB
# enforce it. The policy is ``AS RESTRICTIVE`` so it **ANDs** with ``chunk_source_read`` (a second
# permissive policy would OR, weakening isolation). The per-txn GUC ``app.allowed_knowledge_scopes``
# mirrors ``app.allowed_sources``: unset -> ``current_setting`` is NULL -> denies (fail closed); a
# scope list -> ``tags``-overlap; the explicit sentinel ``'*'`` -> unrestricted (the internal/eval
# opt-out — the public path always resolves a real scope list, never ``'*'``).
_SCOPE_GUC = "app.allowed_knowledge_scopes"
_CHUNK_SCOPE_POLICY = "chunk_scope_read"
_CURATED_SCOPE_POLICY = "curated_knowledge_entry_scope_read"


def apply_chunk_scope_rls(conn: Connection) -> None:
    """Add the RESTRICTIVE knowledge-scope policy to ``chunk`` (ADR-0014, mig 0014). Idempotent.

    Composes with ``apply_chunk_rls``'s source policy via AND. Requires that policy to already exist
    (``chunk`` RLS ``ENABLE``d); this only adds the second, restrictive predicate.

    Fail-closed (D3, migration 0014): the policy is pure ``tags``-overlap, with **no**
    ``cardinality(tags) = 0`` floor. An empty-tags chunk overlaps nothing and is therefore visible
    to **no** scope — "public" is the explicit ``general`` tag, never empty tags. (The old floor
    made an untagged chunk global; dropping the last tag then leaked a page cross-scope. Rules
    1/2/5/7 guarantee every active chunk carries >=1 recognised tag, so the floor was unreachable in
    the intended state; this makes it fail-closed if that ever regresses.) ``'*'`` -> unrestricted
    opt-out (internal/eval + already-authorized parent expansion); unset -> ``string_to_array(NULL,
    ',')`` is NULL -> overlap denies (fail closed).
    """
    conn.execute(text("ALTER TABLE chunk ENABLE ROW LEVEL SECURITY"))
    conn.execute(text(f"DROP POLICY IF EXISTS {_CHUNK_SCOPE_POLICY} ON chunk"))
    conn.execute(
        text(
            f"CREATE POLICY {_CHUNK_SCOPE_POLICY} ON chunk AS RESTRICTIVE FOR SELECT "
            f"USING (current_setting('{_SCOPE_GUC}', true) = '*' "
            f"OR tags && string_to_array(current_setting('{_SCOPE_GUC}', true), ','))"
        )
    )


def drop_chunk_scope_rls(conn: Connection) -> None:
    """Reverse ``apply_chunk_scope_rls`` (keeps the source policy + RLS enable state).
    Idempotent."""
    conn.execute(text(f"DROP POLICY IF EXISTS {_CHUNK_SCOPE_POLICY} ON chunk"))


# --- Option A / ADR-0020 D1: directed-connection routing label policy on ``chunk`` ------------
# The raw-labels axis (migration 0016). A RESTRICTIVE policy keyed on ``app.allowed_labels`` that
# mirrors ``chunk_scope_read`` in SHAPE but is deliberately a **no-op until the GUC is set** — the
# retrieval path that sets ``app.allowed_labels`` lands in a later substep (9.4.1 / Stage 6). Unlike
# the scope GUC (which fails CLOSED on unset so a dropped call denies), labels are the
# routing/relevance axis, NOT the access boundary: source isolation (``chunk_source_read``, lock 1)
# and customer-scope isolation (``chunk_scope_read``, lock 2) remain the fail-closed enforcement
# fence. So this policy opts out when the GUC is unset (NULL/empty) and on the explicit ``'*'``
# sentinel, and only overlaps when a real connection-label list is set.
_LABELS_GUC = "app.allowed_labels"
_CHUNK_LABELS_POLICY = "chunk_labels_read"


def apply_chunk_labels_rls(conn: Connection) -> None:
    """Add the RESTRICTIVE directed-connection labels policy to ``chunk`` (ADR-0020 D1, mig 0016).

    Composes (ANDs) with ``chunk_source_read`` + ``chunk_scope_read``; requires chunk RLS enabled.
    No-op until ``app.allowed_labels`` is set (9.4.1): unset/empty -> opt out; ``'*'`` -> opt out;
    a real list -> ``labels``-overlap. Idempotent.
    """
    conn.execute(text("ALTER TABLE chunk ENABLE ROW LEVEL SECURITY"))
    conn.execute(text(f"DROP POLICY IF EXISTS {_CHUNK_LABELS_POLICY} ON chunk"))
    conn.execute(
        text(
            f"CREATE POLICY {_CHUNK_LABELS_POLICY} ON chunk AS RESTRICTIVE FOR SELECT "
            f"USING (coalesce(current_setting('{_LABELS_GUC}', true), '') = '' "
            f"OR current_setting('{_LABELS_GUC}', true) = '*' "
            f"OR labels && string_to_array(current_setting('{_LABELS_GUC}', true), ','))"
        )
    )


def drop_chunk_labels_rls(conn: Connection) -> None:
    """Reverse ``apply_chunk_labels_rls`` (keeps the source + scope policies + RLS enable state).

    Safe on any host: the policy is a no-op (unset GUC opts out), so dropping it loosens nothing —
    source + scope isolation (locks 1-2) are untouched. Idempotent."""
    conn.execute(text(f"DROP POLICY IF EXISTS {_CHUNK_LABELS_POLICY} ON chunk"))


def apply_curated_scope_rls(conn: Connection) -> None:
    """Add the RESTRICTIVE knowledge-scope policy to ``curated_knowledge_entry`` (ADR-0014).

    Same GUC as ``chunk``, plus ``cardinality(tags) = 0`` — an empty-tags curated entry is global
    ("every scope", ADR-0011) and stays visible under any real scope list; only a *tagged* curated
    entry is isolated. ``'*'`` and unset behave as on ``chunk``. Composes (AND) with 0009's
    permissive ``*_reader_read`` policy, so this only *subtracts* visibility; it never grants a new
    role access. Idempotent.
    """
    conn.execute(text("ALTER TABLE curated_knowledge_entry ENABLE ROW LEVEL SECURITY"))
    conn.execute(text(f"DROP POLICY IF EXISTS {_CURATED_SCOPE_POLICY} ON curated_knowledge_entry"))
    conn.execute(
        text(
            f"CREATE POLICY {_CURATED_SCOPE_POLICY} ON curated_knowledge_entry "
            f"AS RESTRICTIVE FOR SELECT "
            f"USING (current_setting('{_SCOPE_GUC}', true) = '*' "
            f"OR cardinality(tags) = 0 "
            f"OR tags && string_to_array(current_setting('{_SCOPE_GUC}', true), ','))"
        )
    )


def drop_curated_scope_rls(conn: Connection) -> None:
    """Reverse ``apply_curated_scope_rls``. Idempotent."""
    conn.execute(text(f"DROP POLICY IF EXISTS {_CURATED_SCOPE_POLICY} ON curated_knowledge_entry"))


# Phase 13.1 — the reader's non-chunk read set. On Supabase the PostgREST roles anon/authenticated
# hold blanket GRANT SELECT on every public table, so RLS (not its absence) is what keeps the corpus
# private: an RLS-enabled table with no matching policy default-denies those roles. So we keep RLS
# ENABLED on the non-chunk tables (anon stays out) and add a policy scoped to rag_reader for the
# tables retrieval reads. Disabling RLS instead would expose every row to the public anon REST
# endpoint — the exact failure this guards against.
_READER_READ_TABLES = ("page_source", "page_restriction", "curated_knowledge_entry")


def _non_chunk_tables() -> list[str]:
    """Every mapped table except ``chunk``.

    Derived from ORM metadata so a new table is covered automatically. ``alembic_version`` is
    Alembic's own table (not in ``Base.metadata``), so it is out of scope. Uses ``.tables``
    (unordered) not ``.sorted_tables``: an ``ALTER TABLE`` needs no order, and the metadata has
    intentional circular FKs (page_source <-> document_version) that make ``sorted_tables`` warn.
    """
    return sorted(name for name in Base.metadata.tables if name != "chunk")


def _table_exists(conn: Connection, table: str) -> bool:
    """True iff ``public.<table>`` exists in the connected database.

    ``_non_chunk_tables`` derives from live ORM metadata, so it lists every table the CURRENT
    models know about — including tables created by a LATER migration (e.g. ``chat_session``,
    migration 0017). When the 0009 enable/disable helpers run at their own point in the chain (a
    fresh ``upgrade head``, or a round-trip test that downgrades through 0009 and back), such a
    table does not exist yet, and a bare ``ALTER TABLE`` would raise ``UndefinedTable``. Guarding
    on existence keeps these helpers valid for any table added after 0009, which then enables its
    own RLS in its own migration — the chain stays reversible (never-bend rule 11)."""
    return (
        conn.execute(text("SELECT to_regclass(:t)"), {"t": f"public.{table}"}).scalar() is not None
    )


def enable_non_chunk_rls(conn: Connection) -> None:
    """Enable RLS on every non-chunk table so anon/authenticated are default-denied.

    Idempotent, and safe-by-default on a fresh managed deploy: with no policy an RLS-enabled table
    yields zero rows to any non-owner, non-BYPASSRLS role (the Supabase PostgREST roles). The owner
    (writer) bypasses RLS by ownership (ADR-0013); rag_reader is let back in only where needed, by
    ``apply_reader_rls``. Skips a not-yet-created table (see ``_table_exists``).
    """
    for table in _non_chunk_tables():
        if _table_exists(conn, table):
            conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))


def disable_non_chunk_rls(conn: Connection) -> None:
    """Reverse ``enable_non_chunk_rls`` (migration 0009 downgrade). Idempotent.

    WARNING: on Supabase this re-exposes every non-chunk table to the public anon REST role (which
    holds GRANT SELECT), because RLS is the only thing fencing those roles out. Only downgrade a
    store with no PostgREST/anon exposure (local docker, RDS fallback). Skips a not-yet-created
    table (see ``_table_exists``).
    """
    for table in _non_chunk_tables():
        if _table_exists(conn, table):
            conn.execute(text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))


def apply_reader_rls(conn: Connection, *, role: str = "rag_reader") -> None:
    """Let rag_reader read its non-chunk tables while anon/authenticated stay denied.

    Adds a ``FOR SELECT TO <role> USING (true)`` policy to each ``_READER_READ_TABLES`` entry (the
    exact set retrieval reads via the reader session: page ACL + curated layer). Because the policy
    names rag_reader, no other role matches it, so anon/authenticated stay default-denied despite a
    GRANT SELECT. App-layer scope/ACL filtering is unchanged — these tables are read in full and
    filtered in code, so ``USING (true)`` is correct here (chunk keeps its stricter source-keyed
    policy).

    Skips policy creation when ``role`` does not exist yet (a fresh ``alembic upgrade`` runs before
    the role is provisioned); ``setup_supabase.py provision-reader`` re-runs this once it exists.
    Idempotent. ``role`` is a trusted deployment constant, validated as a plain identifier because
    ``CREATE POLICY`` cannot bind an identifier.
    """
    if not role.replace("_", "").isalnum():
        raise ValueError(f"unsafe reader role name: {role!r}")
    role_exists = conn.execute(
        text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}
    ).scalar()
    for table in _READER_READ_TABLES:
        conn.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        conn.execute(text(f"DROP POLICY IF EXISTS {table}_reader_read ON {table}"))
        if role_exists:
            conn.execute(
                text(
                    f"CREATE POLICY {table}_reader_read ON {table} "
                    f"FOR SELECT TO {role} USING (true)"
                )
            )


def drop_reader_rls(conn: Connection) -> None:
    """Reverse ``apply_reader_rls``: drop the reader read policies (leaves the RLS enable state)."""
    for table in _READER_READ_TABLES:
        conn.execute(text(f"DROP POLICY IF EXISTS {table}_reader_read ON {table}"))


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
    if not exists:
        conn.execute(
            text(
                f"CREATE ROLE {role} LOGIN PASSWORD '{esc}' "
                "NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS"
            )
        )
    else:
        # Re-provision: reset ONLY the password. The attributes were fixed at CREATE and never
        # change, and re-asserting NOSUPERUSER/NOBYPASSRLS here is rejected by managed Postgres —
        # Supabase's non-superuser `postgres` cannot ALTER role attributes ("only SUPERUSER may
        # alter roles with the SUPERUSER attribute"). A bare PASSWORD reset keeps the login
        # deterministic on the managed store without dropping the cluster-global role. (13.2.)
        conn.execute(text(f"ALTER ROLE {role} PASSWORD '{esc}'"))
    conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
    conn.execute(text(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}"))
    conn.execute(
        text(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {role}")
    )
    _grant_extensions_access(conn, role=role)


def _grant_extensions_access(conn: Connection, *, role: str) -> None:
    """Let the reader resolve pgvector's types when they live in an ``extensions`` schema.

    Supabase installs pgvector into ``extensions`` (not ``public``); a plain ``rag_reader`` has no
    ``USAGE`` there and ``extensions`` is off its ``search_path``, so every dense query
    (``embedding::halfvec(dim)``) fails as the reader with ``type "halfvec" does not exist`` /
    ``permission denied for schema extensions``. Because retrieval MUST run as the non-owner reader
    (ADR-0004), that breaks live semantic search. We only act when an ``extensions`` schema exists —
    a local/RDS install puts pgvector in ``public``, where the reader is already covered by the
    ``GRANT USAGE ON SCHEMA public`` above.

    On Supabase the owner role is permission-gated off both the supabase-owned ``extensions`` schema
    (the ``GRANT``) and, on some clusters, the role config default (the ``ALTER ROLE … SET``). Each
    statement is wrapped in its own SAVEPOINT so a permission failure leaves the surrounding
    provisioning transaction intact and any partial success is retained; the operator applies
    whatever was refused out of band (see the reader-provisioning runbook). ``role`` is already
    validated by the caller as a plain identifier.
    """
    ext_exists = conn.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'extensions'")
    ).scalar()
    if not ext_exists:
        return
    for stmt in (
        f"ALTER ROLE {role} SET search_path = public, extensions",
        f"GRANT USAGE ON SCHEMA extensions TO {role}",
    ):
        sp = conn.begin_nested()
        try:
            conn.execute(text(stmt))
            sp.commit()
        except ProgrammingError:
            # insufficient_privilege on managed Postgres — operator runs it manually (see runbook).
            sp.rollback()
