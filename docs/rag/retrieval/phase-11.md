# Phase 11.1a — customer/knowledge-scope isolation backstop (retrieval-side)

**Status:** 🟩 code + tests done via TDD (2026-09-10), committed on `feat/rag-phase-3.5`; **migration
`0010` NOT yet applied to live Supabase** (live head `0009`) — apply is a plain `alembic upgrade head`.
Design of record: [`../../adr/0014-Customer-Scope-Isolation-Backstop.md`](../../adr/0014-Customer-Scope-Isolation-Backstop.md).
Distinct axis from Phase 13.1 ([`phase-13.md`](./phase-13.md), reader read-access) and from the source
policy (ADR-0004).

## The problem

The `mews`/`opera-cloud`/`toast`/`general` boundary (carried as `obi-*-test` tags) was enforced **only**
by the app-layer `tags && :scopes` predicate in `search_repo._base_filters`, gated behind
`enable_knowledge_scope_filtering` — which **failed open**: flag off, or one dropped predicate, returned
every customer's rows to everyone. All four scopes share one `source_id`, so ADR-0004's
`chunk_source_read` does not separate them, and `curated_knowledge_entry` had no tenant policy. Source
isolation fails *closed*; the customer axis did not.

## The fix (scope-GUC RLS — a second, RESTRICTIVE axis)

A DB backstop that mirrors the source axis, so a dropped predicate or a flag flip can no longer leak:

- **`platform/db/schema.py::apply_chunk_scope_rls`** — a second policy `chunk_scope_read` on `chunk`,
  **`AS RESTRICTIVE`** so it **ANDs** with `chunk_source_read` (a permissive policy would OR, weakening
  isolation). Keyed on a new per-txn GUC `app.allowed_knowledge_scopes`. `apply_curated_scope_rls` adds
  the analogue on `curated_knowledge_entry`.
- **`platform/db/schema.py`** predicate: `current_setting('app.allowed_knowledge_scopes', true) = '*'
  OR cardinality(tags) = 0 OR tags && string_to_array(current_setting(...), ',')`. Unset GUC → tagged
  rows denied (**fail closed**); untagged chunk → global (single-tenant/untagged corpora keep working);
  `'*'` → explicit unrestricted opt-out.
- **`retrieval/infrastructure/search_repo.py::apply_knowledge_scope`** — sets the GUC (bound param, never
  interpolated), `'*'` when `None`. Exported from the retrieval facade (`retrieval/__init__.py`).
- **`retrieval/application/retriever.py::_search`** — calls `apply_knowledge_scope(session,
  knowledge_scopes)` on **every** reader txn, from the raw argument, **independent of the flag**. The
  flag now governs only the redundant app predicate (defense-in-depth + ADR-0011 Decision-1). Also set in
  `fetch_parent_texts` (as `'*'` — the parent ids already came from a scoped, permitted search).
- **`rag_agent/infrastructure/curated_knowledge_repo.py::fetch_curated_entries`** — sets the same GUC
  before its read, so the curated layer is isolated at the DB too.
- **`alembic/versions/0010_customer_scope_rls.py`** — `upgrade` = apply both scope policies; `downgrade`
  = drop them (leaves `chunk_source_read` + RLS enable state intact).

## Contract change (intentional)

Passing `knowledge_scopes` now isolates *tagged* content at the DB **even with the flag off** — before,
flag-off ignored the argument entirely (the fail-open hole). `test_flag_off_still_enforces_scope_via_rls_backstop`
replaces the old `..._ignores_knowledge_scopes_argument` test to lock this in.

## Tests

- `confluence_sync/tests/test_customer_isolation_backstop.py` — direct reader reads with **no app
  predicate**: cross-customer chunk denied via the GUC alone; unset GUC fails closed (tagged);
  `'*'` restores unrestricted; untagged chunk stays global; and the curated analogue (tagged isolated,
  empty-tags global, unset fails closed) on an isolated RLS setup.
- `platform/db/tests/test_migration_0010_scope_rls.py` — real Alembic up/down/up: both policies present
  and **`RESTRICTIVE`**, gone on downgrade, back on re-upgrade; `chunk_source_read` + RLS survive.
- `confluence_sync/tests/test_retrieval_knowledge_scope.py` — updated for the new contract (flag-off
  enforces; no-scopes = unrestricted `'*'`).
- Gate: `make check` **501 passed** (local DSN override), boundaries clean, ruff/format/pyright clean.

## Not this file / still open

- **Live apply:** run `uv run alembic upgrade head` on Supabase (`0009` → `0010`). The reader already has
  the pgvector `extensions` grant (P0 closed 2026-09-10), so no extra operator step.
- **Not covered here:** the per-user→customer edge binding (still one shared `CHAT_API_KEY`) — Phase
  11.1c + the deferred AWS deploy. The scope a request carries is still trusted from the caller.
- **Optional follow-up:** extend `setup_supabase.py verify-isolation` to exercise the scope GUC live
  (as 13.2 did for the source axis).
