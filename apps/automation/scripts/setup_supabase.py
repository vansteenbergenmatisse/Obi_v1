"""One-off operator CLI: stand up the RAG schema + roles on managed Postgres (Supabase / RDS).

Phase 6 / ADR-0013. Runs the *non-Alembic* half of the cutover — Alembic itself is driven
separately (``uv run alembic upgrade head``) between ``preflight`` and ``provision-reader``. Every
phase is idempotent and safe to re-run. **No secret is ever printed or logged**: the generated
``rag_reader`` password is written only into the gitignored root ``.env`` (``DATABASE_READER_URL``).

Order (from ``apps/automation``, with the writer/owner ``DATABASE_URL`` set in the root ``.env``):

    uv run python scripts/setup_supabase.py preflight          # step 1: identity + pgvector gate
    uv run alembic upgrade head                                # step 2: schema as the table-owner
    uv run python scripts/setup_supabase.py provision-reader   # step 3: rag_reader + reader DSN
    # ... load the corpus (pg_dump --data-only local -> psql restore) ...
    uv run python scripts/setup_supabase.py verify-isolation   # step 5: RLS default-deny holds live

``preflight`` exits non-zero (and refuses to go further) if pgvector < 0.8.0, per the plan's gate.
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.platform.config import get_settings
from app.platform.db import engine as engine_mod
from app.platform.db import schema

_MIN_PGVECTOR = (0, 8, 0)
_READER_ROLE = "rag_reader"
_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"  # repo-root .env (gitignored)


def _pgvector_version(conn) -> tuple[str, tuple[int, ...]]:
    raw = conn.execute(
        text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    ).scalar_one_or_none()
    if raw is None:
        return ("<not installed>", (0,))
    parts = tuple(int(p) for p in raw.split(".") if p.isdigit())
    return (raw, parts)


def _mask(url: str) -> str:
    u = make_url(url)
    return u.render_as_string(hide_password=True)


def preflight() -> int:
    """Verify connectivity, DB identity, current role, and the pgvector version gate."""
    eng = engine_mod.get_engine()
    with eng.connect() as conn:
        db = conn.execute(text("SELECT current_database()")).scalar_one()
        user = conn.execute(text("SELECT current_user")).scalar_one()
        is_super = conn.execute(text("SELECT current_setting('is_superuser')")).scalar_one()
        pgv_raw, pgv = _pgvector_version(conn)
        # Guard the table read: a WHERE clause can't shield the FROM from name resolution, so on a
        # pre-migration DB `SELECT ... FROM alembic_version` raises UndefinedTable. Check existence
        # first (to_regclass yields NULL when absent), then read only if it's there.
        has_alembic = conn.execute(
            text("SELECT to_regclass('alembic_version')")
        ).scalar_one_or_none()
        head = (
            conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
            if has_alembic is not None
            else None
        )

    print(f"connected: db={db!r} role={user!r} is_superuser={is_super}")
    print(f"host      : {_mask(get_settings().database_url)}")
    print(f"pgvector  : {pgv_raw}")
    print(f"alembic   : {head or '<no alembic_version table yet — run upgrade head>'}")

    if pgv < _MIN_PGVECTOR:
        print(
            f"FAIL: pgvector {pgv_raw} < 0.8.0 required (hnsw.iterative_scan). "
            "Stopping before migration — decide a mitigation first.",
            file=sys.stderr,
        )
        return 2
    print("OK: pgvector >= 0.8.0 — safe to migrate.")
    return 0


def _derive_reader_url(owner_url: str, password: str) -> str:
    """Reader DSN = owner host/db, but the rag_reader role and its own password.

    Supabase's pooler username is ``<role>.<project_ref>``; a custom role authenticates as
    ``rag_reader.<project_ref>``. A direct (non-pooler) DSN has a plain ``postgres`` username, so
    the reader is plain ``rag_reader``. We carry over the query string (e.g. ``sslmode=require``).
    """
    u = make_url(owner_url)
    owner_user = u.username or ""
    if "." in owner_user:  # pooler form: base.<ref>
        ref = owner_user.split(".", 1)[1]
        reader_user = f"{_READER_ROLE}.{ref}"
    else:
        reader_user = _READER_ROLE
    return u.set(username=reader_user, password=password).render_as_string(hide_password=False)


def _write_reader_dsn(reader_url: str) -> None:
    """Set DATABASE_READER_URL in the root .env in place, preserving every other line."""
    lines = _ROOT_ENV.read_text().splitlines() if _ROOT_ENV.exists() else []
    quoted = f'DATABASE_READER_URL="{reader_url}"'
    out, found = [], False
    for ln in lines:
        if ln.startswith("DATABASE_READER_URL="):
            out.append(quoted)
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(quoted)
    _ROOT_ENV.write_text("\n".join(out) + "\n")


def provision_reader() -> int:
    """Create/refresh the non-owner rag_reader role, re-assert RLS, and write the reader DSN."""
    password = secrets.token_urlsafe(24)
    eng = engine_mod.get_engine()
    with eng.begin() as conn:
        schema.ensure_reader_role(conn, role=_READER_ROLE, password=password)
        # Belt-and-suspenders: migrations already apply this, but re-assert ENABLE + NO FORCE so a
        # partially-migrated instance still ends RLS-correct (ADR-0013). Idempotent.
        schema.apply_chunk_rls(conn)

    reader_url = _derive_reader_url(get_settings().database_url, password)
    _write_reader_dsn(reader_url)
    print(f"rag_reader ready; DATABASE_READER_URL written to {_ROOT_ENV}")
    print(f"reader DSN: {_mask(reader_url)}")  # password masked
    print("Reload settings/engines (new process) before verify-isolation.")
    return 0


def verify_isolation() -> int:
    """Prove the ADR-0004 read-path guarantee holds live: owner sees rows, reader is default-deny.

    Meaningful only once the corpus is loaded (an empty chunk table reads 0 either way). Reads the
    real ``source_id`` set from the owner side, then checks the reader: no GUC -> 0 rows; GUC set to
    a real source -> only that source's rows; GUC set to a bogus source -> 0 rows.
    """
    eng = engine_mod.get_engine()
    with eng.connect() as conn:
        total = conn.execute(text("SELECT count(*) FROM chunk")).scalar_one()
        sources = [
            r[0]
            for r in conn.execute(
                text("SELECT DISTINCT source_id FROM chunk ORDER BY source_id")
            ).all()
        ]
    if total == 0:
        print("SKIP: chunk table is empty — load the corpus before verifying isolation.")
        return 1
    if not sources:
        print("FAIL: rows exist but no source_id found.", file=sys.stderr)
        return 3

    real = sources[0]
    engine_mod.get_reader_engine.cache_clear()
    engine_mod.get_reader_sessionmaker.cache_clear()
    reader = engine_mod.get_reader_sessionmaker()

    with reader() as s:
        no_guc = s.execute(text("SELECT count(*) FROM chunk")).scalar_one()
    with reader() as s:
        # SET LOCAL cannot bind params; set_config(name, value, is_local=true) is the transaction-
        # scoped equivalent that can (mirrors retrieval's apply_source_scope).
        s.execute(text("SELECT set_config('app.allowed_sources', :v, true)"), {"v": real})
        scoped = s.execute(text("SELECT count(*) FROM chunk")).scalar_one()
    with reader() as s:
        s.execute(
            text("SELECT set_config('app.allowed_sources', :v, true)"),
            {"v": "confluence:__nonexistent__"},
        )
        bogus = s.execute(text("SELECT count(*) FROM chunk")).scalar_one()

    print(f"owner sees        : {total} chunks across sources {sources}")
    print(f"reader, no GUC    : {no_guc}  (expect 0 — default-deny)")
    print(f"reader, {real!r}: {scoped}  (expect > 0 — scoped access)")
    print(f"reader, bogus src : {bogus}  (expect 0 — non-matching source excluded)")

    ok = no_guc == 0 and scoped > 0 and bogus == 0
    if not ok:
        print("FAIL: RLS default-deny / scoping did not hold as expected.", file=sys.stderr)
        return 4
    print("OK: ADR-0004 read-path isolation holds on this instance.")
    return 0


_PHASES = {
    "preflight": preflight,
    "provision-reader": provision_reader,
    "verify-isolation": verify_isolation,
}


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in _PHASES:
        print(f"usage: setup_supabase.py {{{'|'.join(_PHASES)}}}", file=sys.stderr)
        return 64
    return _PHASES[argv[0]]()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
