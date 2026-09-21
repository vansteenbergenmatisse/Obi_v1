"""One-off operator CLI: stand up the RAG schema + roles on managed Postgres (Supabase / RDS).

Phase 6 / ADR-0013. Runs the *non-Alembic* half of the cutover — Alembic itself is driven
separately (``uv run alembic upgrade head``) between ``preflight`` and ``provision-reader``. Every
phase is idempotent and safe to re-run. **No secret is ever printed or logged**: the generated
``rag_reader`` password is written only into the gitignored root ``.env`` (``DATABASE_READER_URL``).

Order (from ``backend``, with the writer/owner ``DATABASE_URL`` set in the root ``.env``):

    uv run python scripts/setup_supabase.py preflight          # step 1: identity + pgvector gate
    uv run alembic upgrade head                                # step 2: schema as the table-owner
    uv run python scripts/setup_supabase.py provision-reader   # step 3: rag_reader + reader DSN
    # ... load the corpus (pg_dump --data-only local -> psql restore) ...
    uv run python scripts/setup_supabase.py verify-isolation   # step 5: RLS default-deny holds live

``preflight`` exits non-zero (and refuses to go further) if pgvector < 0.8.0, per the plan's gate.

⚠️ Fresh Supabase reader: ``provision-reader`` *attempts* the pgvector ``extensions`` GRANT
(``schema._grant_extensions_access``) but it **no-ops on Supabase** — our owner role cannot grant on
the supabase-owned ``extensions`` schema. Until an operator runs, by hand, ``GRANT USAGE ON SCHEMA
extensions TO rag_reader;`` + ``ALTER ROLE rag_reader SET search_path = public, extensions;``, the
reader cannot cast ``halfvec`` and live semantic search fails. See the cutover runbook (step 3).
"""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.platform.config import get_settings
from schema import engine as engine_mod
from schema import schema

_MIN_PGVECTOR = (0, 8, 0)
_READER_ROLE = "rag_reader"
_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"  # repo-root .env (gitignored)


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
        # Fresh-deploy path (13.2): install the non-chunk reader read policies (migration 0009) now
        # that the role exists in this same transaction. The `alembic upgrade` in step 2 ran before
        # the role, so its apply_reader_rls skipped policy creation (role absent) and only enabled
        # RLS. Re-running here creates the `*_reader_read` policies so the reader sees its page-ACL
        # + curated tables while anon/authenticated stay default-denied. Idempotent.
        schema.apply_reader_rls(conn, role=_READER_ROLE)

    reader_url = _derive_reader_url(get_settings().database_url, password)
    _write_reader_dsn(reader_url)
    print(f"rag_reader ready; DATABASE_READER_URL written to {_ROOT_ENV}")
    print(f"reader DSN: {_mask(reader_url)}")  # password masked
    print("Reload settings/engines (new process) before verify-isolation.")
    return 0


_READER_READ_TABLES = ("page_source", "page_restriction", "curated_knowledge_entry")


def _check_reader_halfvec(reader) -> tuple[bool, str]:
    """The production dense-query path (``embedding::halfvec``) must resolve as the reader.

    On Supabase pgvector lives in the ``extensions`` schema; without ``USAGE`` + it on the reader
    ``search_path`` the reader fails with ``type "halfvec" does not exist`` — so live semantic
    retrieval (which MUST run as the non-owner reader, ADR-0004) is broken even though chunk RLS is
    fine. We return ``(ok, detail)`` instead of raising so the summary can point at the operator
    remediation (NEXT FIXES #1: ``GRANT USAGE ON SCHEMA extensions TO rag_reader`` + ``ALTER ROLE
    rag_reader SET search_path = public, extensions``) rather than a traceback.
    """
    try:
        with reader() as s:
            s.execute(text("SELECT CAST('[1,2,3]' AS halfvec(3))")).scalar_one()
    except SQLAlchemyError as exc:
        return False, f"reader CANNOT resolve halfvec ({type(exc).__name__}) — retrieval broken"
    return True, "reader resolves halfvec (dense-query path OK)"


def _check_reader_non_chunk(reader, owner_page_sources: int) -> tuple[bool, str]:
    """The reader must read its page-ACL + curated tables (migration 0009 ``*_reader_read`` policy).

    ``page_source`` is the discriminating table: with the corpus loaded the owner sees > 0 rows, and
    ``apply_reader_rls``'s ``USING (true)`` policy lets the reader see the same count. If the reader
    sees 0 while the owner sees rows, the reader is default-denied (0009 not applied / policy
    missing) → the page ACL fails open and the curated layer goes dark. ``page_restriction`` /
    ``curated_knowledge_entry`` may legitimately be empty, so they are reported, not asserted.
    """
    with reader() as s:
        counts = {
            t: s.execute(text(f"SELECT count(*) FROM {t}")).scalar_one()  # noqa: S608 — const table
            for t in _READER_READ_TABLES
        }
    detail = ", ".join(f"{t}={n}" for t, n in counts.items())
    ok = counts["page_source"] == owner_page_sources
    if not ok:
        return False, f"reader default-DENIED on page_source ({detail}; owner={owner_page_sources})"
    return True, f"reader reads its non-chunk tables ({detail})"


def _check_anon_denied(conn) -> tuple[bool, str]:
    """Confirm Supabase's public REST role ``anon`` stays default-denied despite ``GRANT SELECT``.

    Only meaningful where an ``anon`` role exists (live Supabase); a local/RDS store has none, so
    we skip (reported as pass). Impersonating ``anon`` needs owner membership; if the owner is not a
    member we cannot prove it here, and say so rather than assert.
    """
    if not conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = 'anon'")).scalar():
        return True, "no `anon` role on this instance — anon-denied check N/A (skipped)"
    try:
        conn.execute(text("SET ROLE anon"))
    except SQLAlchemyError:
        return True, "owner is not a member of `anon` — cannot impersonate to prove (skipped)"
    try:
        chunk_n = conn.execute(text("SELECT count(*) FROM chunk")).scalar_one()
        page_n = conn.execute(text("SELECT count(*) FROM page_source")).scalar_one()
    finally:
        conn.execute(text("RESET ROLE"))
    ok = chunk_n == 0 and page_n == 0
    detail = f"anon sees chunk={chunk_n} page_source={page_n} (expect 0/0)"
    return ok, ("anon stays default-denied — " + detail if ok else "anon LEAK — " + detail)


def _check_reader_scope_axis(eng, reader, real_source: str) -> tuple[bool, str]:
    """Prove the ADR-0014 / migration-0010 knowledge-scope backstop: a chunk *tagged* for one
    customer scope is invisible to the reader under any other scope, and visible under its own.

    Distinct from the source axis above: that isolates by ``source_id`` (``app.allowed_sources``);
    this isolates by knowledge-scope tag (``app.allowed_knowledge_scopes``, a RESTRICTIVE policy
    that ANDs on top). Meaningful only on a *tagged* corpus — an all-untagged corpus
    (``cardinality(tags) = 0``) is global by design, so we report a skip-as-pass. The owner bypasses
    RLS, so we read a real tag from the owner side, then count as the reader filtered to rows
    carrying that tag: under the matching scope > 0; under a bogus scope 0 (tagged rows drop out).
    """
    with eng.connect() as conn:
        tag = conn.execute(
            text(
                "SELECT t FROM (SELECT DISTINCT unnest(tags) AS t FROM chunk) u "
                "WHERE t <> '' ORDER BY t LIMIT 1"
            )
        ).scalar()
    if tag is None:
        return True, "no tagged chunks — scope-axis check N/A (skipped)"

    with reader() as s:
        s.execute(text("SELECT set_config('app.allowed_sources', :v, true)"), {"v": real_source})
        s.execute(text("SELECT set_config('app.allowed_knowledge_scopes', :v, true)"), {"v": tag})
        in_scope = s.execute(
            text("SELECT count(*) FROM chunk WHERE :t = ANY(tags)"), {"t": tag}
        ).scalar_one()
    with reader() as s:
        s.execute(text("SELECT set_config('app.allowed_sources', :v, true)"), {"v": real_source})
        s.execute(
            text("SELECT set_config('app.allowed_knowledge_scopes', :v, true)"),
            {"v": "obi-__nonexistent__-test"},
        )
        out_scope = s.execute(
            text("SELECT count(*) FROM chunk WHERE :t = ANY(tags)"), {"t": tag}
        ).scalar_one()

    ok = in_scope > 0 and out_scope == 0
    detail = f"tag {tag!r}: in-scope={in_scope} (expect > 0), out-of-scope={out_scope} (expect 0)"
    return ok, ("scope backstop holds — " + detail if ok else "scope LEAK — " + detail)


def verify_isolation() -> int:
    """Prove the ADR-0004 read-path guarantee holds live: owner sees rows, reader is default-deny.

    Meaningful only once the corpus is loaded (an empty chunk table reads 0 either way). Reads the
    real ``source_id`` set from the owner side, then checks the reader: no GUC -> 0 rows; GUC set to
    a real source -> only that source's rows; GUC set to a bogus source -> 0 rows. Then (13.2) also
    checks the reader can resolve pgvector types (dense-query path), can read its non-``chunk``
    page-ACL + curated tables (migration 0009), and that an ``anon``-like public role stays denied.
    Finally (ADR-0014 / migration 0010) it proves the knowledge-scope backstop: a chunk tagged for
    one customer scope is invisible to the reader under any other scope (the source-axis checks opt
    out of that RESTRICTIVE policy via the ``'*'`` wildcard so they still measure the source axis).
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
        owner_page_sources = conn.execute(text("SELECT count(*) FROM page_source")).scalar_one()
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
        # ADR-0014 / 0010: the RESTRICTIVE scope policy ANDs with the source policy, so a *tagged*
        # corpus needs the scope GUC or every tagged row drops out and this source-axis count reads
        # 0. Opt out with '*' here so this block isolates the *source* axis; the scope axis is
        # proven separately below.
        s.execute(text("SELECT set_config('app.allowed_knowledge_scopes', '*', true)"))
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

    chunk_ok = no_guc == 0 and scoped > 0 and bogus == 0

    # 13.2: dense-query path + non-chunk reader reads + anon-denied.
    halfvec_ok, halfvec_detail = _check_reader_halfvec(reader)
    non_chunk_ok, non_chunk_detail = _check_reader_non_chunk(reader, owner_page_sources)
    with eng.connect() as conn:
        anon_ok, anon_detail = _check_anon_denied(conn)
    # ADR-0014 / 0010: prove the scope backstop — a *tagged* chunk is isolated to its own scope.
    scope_ok, scope_detail = _check_reader_scope_axis(eng, reader, real)
    print(f"reader halfvec    : {halfvec_detail}")
    print(f"reader non-chunk  : {non_chunk_detail}")
    print(f"anon role         : {anon_detail}")
    print(f"scope axis        : {scope_detail}")

    if not chunk_ok:
        print("FAIL: RLS default-deny / scoping did not hold as expected.", file=sys.stderr)
        return 4
    if not halfvec_ok:
        print(
            "FAIL: reader cannot run vector queries — run `GRANT USAGE ON SCHEMA extensions TO "
            "rag_reader;` + `ALTER ROLE rag_reader SET search_path = public, extensions;` "
            "(NEXT FIXES #1).",
            file=sys.stderr,
        )
        return 5
    if not non_chunk_ok:
        print(
            "FAIL: reader is denied on page_source — apply migration 0009 / provision-reader "
            "(page ACL fails open otherwise).",
            file=sys.stderr,
        )
        return 6
    if not anon_ok:
        print("FAIL: an anon-like public role can read the corpus — RLS leak.", file=sys.stderr)
        return 7
    if not scope_ok:
        print(
            "FAIL: knowledge-scope backstop leaked — a tagged chunk was visible under the wrong "
            "scope. Apply migration 0010 (chunk/curated *_scope_read RESTRICTIVE policies).",
            file=sys.stderr,
        )
        return 8
    print("OK: ADR-0004 read-path isolation + reader read-access hold on this instance.")
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
