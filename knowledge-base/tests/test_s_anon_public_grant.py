"""Panel s-anon / substep 0.5.5 (Protect: Security batch): Supabase's public roles.

``anon`` and ``authenticated`` hold ``GRANT SELECT`` on every table the moment Supabase
provisions them — that grant is a platform default, not something this codebase creates,
grants, or could locally reproduce (a vanilla local Postgres has no ``anon``/``authenticated``
roles at all; ``scripts/setup_supabase.py`` checks ``pg_roles`` and skips its own anon-Impersonation
check for exactly this reason). What the codebase *can* control, and what this test proves, is
that it never tries to fight that grant by revoking it: the design's whole defense is row
security with no matching policy (default-deny), not privilege revocation. If anyone ever added
a ``REVOKE ... FROM anon`` (or ``authenticated``) to ``schema.py`` or a migration, it would be
redundant at best on Supabase (a superuser-owned migration role cannot revoke a grant Supabase's
own bootstrap re-applies) and a sign the design had drifted from "RLS is the only fence" toward
relying on a revocation this code cannot durably enforce. This is a source-level check — no
database needed — so it is a unit test, not a database test.
"""

from __future__ import annotations

import re
from pathlib import Path

# knowledge-base/ is two levels up from knowledge-base/tests/ (1.1.1-fix: this suite
# now lives under knowledge-base/tests/, not backend/tests/schema/).
_KB_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_SOURCE = _KB_ROOT / "schema" / "schema.py"
_MIGRATIONS_DIR = _KB_ROOT / "migrations" / "versions"

_REVOKE_ANON_PATTERN = re.compile(r"REVOKE\b[^\n;]*\b(anon|authenticated)\b", re.IGNORECASE)
_POLICY_FOR_ANON_PATTERN = re.compile(
    r"(CREATE POLICY|FOR SELECT TO)[^\n;]*\b(anon|authenticated)\b", re.IGNORECASE
)


def _all_migration_sources() -> list[tuple[Path, str]]:
    return [(p, p.read_text()) for p in sorted(_MIGRATIONS_DIR.glob("*.py"))]


def test_s_anon_schema_module_never_revokes_the_supabase_grant() -> None:
    """The reader/RLS helpers in schema.py never REVOKE SELECT from anon or authenticated.

    Supabase grants anon/authenticated blanket SELECT itself; this code's only defense is RLS
    with no matching policy (default-deny), never a revocation of that platform grant."""
    source = _SCHEMA_SOURCE.read_text()
    match = _REVOKE_ANON_PATTERN.search(source)
    assert match is None, (
        f"schema.py must not REVOKE the Supabase anon/authenticated grant: {match}"
    )


def test_s_anon_migrations_never_revoke_the_supabase_grant() -> None:
    """No Alembic migration issues a REVOKE against anon or authenticated.

    Same guard as the schema-module test, applied to every migration file: the upgrade/downgrade
    path relies solely on enabling RLS with no matching policy, never on revoking the platform's
    GRANT SELECT (which a migration role could not durably enforce against Supabase's own
    bootstrap in any case)."""
    offenders = [
        (path.name, match.group(0))
        for path, source in _all_migration_sources()
        if (match := _REVOKE_ANON_PATTERN.search(source)) is not None
    ]
    assert offenders == [], (
        f"migration(s) revoke the Supabase anon/authenticated grant: {offenders}"
    )


def test_s_anon_no_policy_ever_names_anon_or_authenticated() -> None:
    """No CREATE POLICY (schema.py or a migration) targets anon or authenticated directly.

    Every reader/reconcile policy in this codebase is scoped ``TO rag_reader`` (or another named
    app role); none is ever written ``TO anon`` or ``TO authenticated``. Writing one would grant
    those Supabase public roles read access outright, defeating the default-deny design this
    panel protects (a bug distinct from, and worse than, revoking the platform grant)."""
    source = _SCHEMA_SOURCE.read_text()
    schema_offenders = _POLICY_FOR_ANON_PATTERN.findall(source)
    assert schema_offenders == [], (
        f"schema.py grants a policy to anon/authenticated: {schema_offenders}"
    )

    migration_offenders = [
        (path.name, match.group(0))
        for path, source in _all_migration_sources()
        if (match := _POLICY_FOR_ANON_PATTERN.search(source)) is not None
    ]
    assert migration_offenders == [], (
        f"migration(s) grant a policy to anon/authenticated: {migration_offenders}"
    )
