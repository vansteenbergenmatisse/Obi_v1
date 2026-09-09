# Phase 13.1 — reader RLS on non-`chunk` tables (retrieval-side)

**Status:** 🟩 code + tests done via TDD (2026-09-09), UNCOMMITTED; **migration 0009 not yet run
against live Supabase** — until then the reader is still locked out there. Apply steps + verification:
[`../../runbooks/phase-13.1-apply-reader-rls-supabase.md`](../../runbooks/phase-13.1-apply-reader-rls-supabase.md).

## The problem (live, verified)

Retrieval runs as the non-owner `rag_reader` role (`platform/db/engine.py::get_reader_engine`;
fails closed outside offline envs). It reads `page_source` + `page_restriction` (the page ACL, via
`retrieval/infrastructure/search_repo.py::fetch_page_scopes`, lines 202/208) and
`curated_knowledge_entry` (via `rag_agent/infrastructure/curated_knowledge_repo.py`, wired to the
reader sessionmaker in `main.py`). On Supabase all these tables had RLS **enabled with no policy**, so
`rag_reader` (non-BYPASSRLS) got **0 rows** → the page ACL silently **failed open** and the curated
layer went dark. Masked today only because those tables are empty and the corpus is single-space
all-`general`.

## Why "just disable RLS" is unsafe (the security pivot)

Supabase's PostgREST roles `anon` and `authenticated` hold blanket `GRANT SELECT` on **every** public
table (verified live). RLS is therefore the *only* thing keeping the corpus off the public REST API.
Disabling RLS would expose every row to the unauthenticated `anon` role. So the fix keeps RLS **on**.

## The fix (Option B — role-scoped reader policies)

- `platform/db/schema.py::enable_non_chunk_rls` — RLS stays enabled on every non-`chunk` table
  (`anon`/`authenticated` default-denied); safe-by-default on a fresh deploy.
- `platform/db/schema.py::apply_reader_rls` — adds a `FOR SELECT TO rag_reader USING (true)` policy to
  the reader's exact read set (`page_source`, `page_restriction`, `curated_knowledge_entry`). Only
  `rag_reader` matches, so `anon`/`authenticated` stay denied despite their `GRANT SELECT`. Skips
  policy creation if the role doesn't exist yet (fresh deploy migrates before `provision-reader`).
- `drop_reader_rls` / `disable_non_chunk_rls` — downgrade helpers (the latter never to be run against
  Supabase — it re-exposes to `anon`).
- `alembic/versions/0009_reconcile_non_chunk_rls.py` — `upgrade()` = enable + apply_reader_rls;
  `downgrade()` = drop policies + disable (warned).

`chunk` is untouched — its source-keyed default-deny policy (`chunk_source_read`, ADR-0004) still
bites, so read-path source isolation is unchanged. Different axis from Phase 11.1a (customer-scope).

## Tests

- `app/features/confluence_sync/tests/test_reader_rls_reconcile.py` — (1) reader freed by
  `apply_reader_rls` **and** an `anon`-like role (SELECT grant, no BYPASSRLS) STILL reads 0 after the
  fix (the critical no-public-leak assertion; proven meaningful by a mutation check that makes the
  policy public → the assertion fails); (2) `chunk` source isolation intact after the reconcile;
  (3) policy is skipped when the reader role is absent.
- `app/platform/db/tests/test_migration_0009_reader_rls_reconcile.py` — real Alembic up/down/up:
  reader policy appears on upgrade, reverts on downgrade, `chunk` keeps RLS throughout.
- Gate: `make check` **488 passed**; boundaries clean; ruff/format/pyright clean on touched files.

## Applied

- **Applied to live Supabase (2026-09-09):** `uv run alembic upgrade head` → live head `0009`. Verified
  read-only: the 3 `*_reader_read` policies are permissive `SELECT USING(true)` scoped to `{rag_reader}`;
  RLS stays ON on all 12 tables; `anon`/`authenticated` (`NOBYPASSRLS`) have no matching policy;
  `page_source` (9 rows) is now readable by `rag_reader` (was 0 pre-0009). Reader-level smoke: **PASS**
  (proven via catalog + deterministic RLS semantics — a live `rag_reader` *login* was not run: no reader
  password on hand, and a reset is blocked because Supabase's non-superuser `postgres` can't `ALTER`/`SET
  ROLE` the role).

## Still to do

- **13.2** — `setup_supabase.py provision-reader` should call `apply_reader_rls` after creating the
  role (fresh-deploy path), and `verify_isolation` should exercise the reader against
  `page_source`/`page_restriction`/`curated_knowledge_entry` (and confirm an `anon`-like role is
  denied), not just `chunk`. **Also fix the re-provision path:** with the role already present,
  `ensure_reader_role` emits `ALTER ROLE … NOSUPERUSER … NOBYPASSRLS`, which Supabase's `postgres`
  rejects — split the bare `ALTER ROLE … PASSWORD` reset from the attribute assertion.
- **Reader DSN:** `DATABASE_READER_URL` is currently empty; re-issue a `rag_reader` password (bare
  `ALTER ROLE rag_reader PASSWORD …`, ideally via Supabase Studio) before a real Supabase-backed deploy
  or the empirical reader-login smoke. Not needed for local dev (`ENV=local` falls back to the writer).

## Not this file

- The customer-scope fail-closed backstop (mews/opera/toast) — Phase **11.1a** (PLAN.md).
- The tag→answer differentiation pipeline and its live-demonstrability — [`phase-10.md`](./phase-10.md)
  + Phase 13.5 (PLAN.md §0).
