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
- `app/features/confluence_sync/tests/test_reader_vector_access.py` (NEXT FIXES #1/#2, 2026-09-09) —
  (1) reader can cast `halfvec` (production dense-query path, regression guard); (2) when an
  `extensions` schema exists, `ensure_reader_role` grants the reader USAGE on it and puts it on the
  role `search_path` (RED-first); (3) no-`extensions`-schema / re-provision path is a non-erroring
  no-op. Rolled-back transactions keep the shared session DB clean.
- Gate: `make check` **491 passed** (was 488 pre-#1/#2; local DSN override since `.env` points at
  Supabase); boundaries clean; ruff/format/pyright clean on touched files.

## Applied

- **Applied to live Supabase (2026-09-09):** `uv run alembic upgrade head` → live head `0009`. Verified
  read-only: the 3 `*_reader_read` policies are permissive `SELECT USING(true)` scoped to `{rag_reader}`;
  RLS stays ON on all 12 tables; `anon`/`authenticated` (`NOBYPASSRLS`) have no matching policy;
  `page_source` (9 rows) is now readable by `rag_reader` (was 0 pre-0009). Reader-level smoke: **PASS**.
- **Live `rag_reader` LOGIN round-trip (2026-09-09, later pm): PASS.** Password reset via `ALTER ROLE`
  succeeded and `DATABASE_READER_URL` now carries it. The real app path (`get_reader_sessionmaker()`)
  authenticates as `current_user = session_user = rag_reader`, `is_superuser=off`, `rolbypassrls=false`.
  `page_source` → 9 rows. `chunk` → **0 rows with no `app.allowed_sources` GUC, 0 under a bogus scope,
  85 under the real `confluence:default` scope** (RLS default-deny bites; app scope opens it). The
  writer (`postgres`) sees 85 chunks with no GUC (owner bypass) → the reader is a distinct,
  non-bypassing role, with **no fallback to `DATABASE_URL`/writer**. (Supersedes the earlier "login not
  run" caveat.)

## Still to do

- **13.2 — ✅ DONE (2026-09-10, `ec7c372`).** `setup_supabase.py provision-reader` now calls
  `apply_reader_rls` after creating the role (fresh-deploy path installs the 0009 `*_reader_read`
  policies), and `verify_isolation` exercises the reader against
  `page_source`/`page_restriction`/`curated_knowledge_entry` (page_source count vs owner — the
  page-ACL fail-open sentinel), a reader vector-cast/dense-query (`halfvec`) check, **and** confirms
  an `anon`-like role is denied, not just `chunk` — each with a distinct exit code (5=halfvec,
  6=non-chunk, 7=anon). Covered by `confluence_sync/tests/test_verify_isolation_script.py`. The live
  run against Supabase still returns exit 5 until the operator applies the P0 `extensions` grant
  (below). **Re-provision path: ✅ DONE + committed (`96a7511`)** — the CREATE branch keeps the full
  attribute clause; the role-already-present branch is a **bare `ALTER ROLE … PASSWORD`** reset (no
  attribute clauses), so Supabase's non-superuser `postgres` no longer rejects it.
- ~~**Reader DSN:** `DATABASE_READER_URL` is currently empty~~ — ✅ DONE: password re-issued via
  `ALTER ROLE rag_reader PASSWORD …`, `DATABASE_READER_URL` populated, live login smoke PASSES (above).
- **13.5 — live four-scope differentiation: PROVEN end to end (2026-09-09).** The operator's test
  folder (`1671168029`) holds four pages, one `obi-*-test` label each: `obi-general-test`→"General Obi
  information" (`1671069719`), `obi-mews-test`→"Mews Testpage" (`1670971395`), `obi-operacloud-test`→
  "Opera Cloud Testpage" (`1672314881`), `obi-toast-test`→"Toast Testpage" (`1670873122`). All four
  ingested via `sync_page` (`action=indexed`) with `page_source.tags`/`chunk.tags` = their single
  scope. Exact `search_repo` predicate under the reader RLS scope: general-only→General; Mews→Mews+
  General; Opera→Opera+General; Toast→Toast+General — each product returns only its own page plus the
  always-on `obi-general-test` base (ADR-0011 Decision 1); no cross-product leak; the old `general`
  Base corpus never appears. **`source_scope` reconfigured** (`seed_source_scope`): 4 active `page`
  roots (`tags=[]`) for the test pages, 9 old Base roots deactivated → corpus = exactly the 4 pages.
  The old Base pages are dormant (not hard-deleted). Detail: PLAN.md §0 "VERIFIED LIVE" block.
- **Note — ingestion is `source_scope`-driven, not label-driven.** `knowledge_scopes.json` is the
  recognized-label *vocabulary*; the `source_scope` DB table decides which pages sync. A recognized
  label alone does not pull a page in unless a `source_scope` root covers it. Full label-driven
  ingestion (a recognized label anywhere → auto-ingest) would be a new feature, not yet built.
- **🟠 BLOCKER — `rag_reader` cannot run vector retrieval on Supabase (code baked; live GRANT still
  operator-pending).** pgvector's `vector`/`halfvec` types live in the `extensions` schema;
  `rag_reader` has `USAGE = False` there (and `search_path` omits it), so `embedding::halfvec(...)`
  fails for the reader (`type "halfvec" does not exist` / `permission denied for schema extensions`).
  Retrieval must run as the reader (RLS), so live semantic search is broken on Supabase — masked until
  the reader DSN was actually used (was falling back to the writer).
  - **✅ Code (2026-09-09, uncommitted):** `platform/db/schema.py::_grant_extensions_access` (called
    from `ensure_reader_role`, inherited by `provision-reader`) — when an `extensions` schema exists,
    adds it to the reader role `search_path` and `GRANT USAGE ON SCHEMA extensions`, each in its own
    SAVEPOINT so a managed-store permission failure doesn't abort provisioning. On a local/RDS install
    (pgvector in `public`) the reader is already covered and this is a no-op. Regression + RED-first
    tests in `confluence_sync/tests/test_reader_vector_access.py`.
  - **🔴 Live ops STILL PENDING (operator, in Supabase):** `GRANT USAGE ON SCHEMA extensions TO
    rag_reader;` + `ALTER ROLE rag_reader SET search_path = public, extensions;`. The baked code
    no-ops these on Supabase because our owner role can't grant on the supabase-owned `extensions`
    schema — so a live reader still needs them run by hand.
  - The real end-to-end apples/bananas/grapes retrieval (OpenAI + Cohere) was demonstrated as the
    writer to bypass this; isolation held (score high only when the matching product is in scope;
    out-of-scope product never returned). Re-running it as the ACTUAL `rag_reader` is blocked on the
    live ops above.

## Not this file

- The customer-scope fail-closed backstop (mews/opera/toast) — Phase **11.1a** (PLAN.md).
- The tag→answer differentiation pipeline and its live-demonstrability — [`phase-10.md`](./phase-10.md)
  + Phase 13.5 (PLAN.md §0).
