# Runbook — ADR-routing-labels-sole-content-axis production migration & deploy (0014 → head/0018)

**Status: EXECUTED on 2026-10-13.** Production went from `0014` to `0018` and the Path B backend
was redeployed (commit `3178553`; see the two 2026-10-13 ledger entries for the Path B production cutover and
its live verification). The procedure below is kept as the record of how it was done
and as the rollback reference.

Why now: the Path B code (ADR-routing-labels-sole-content-axis) is complete and green locally, but it writes/reads the
`labels` column and assumes the routing-label axis. Production is **reportedly at migration `0014`**
(owner-attested; a read-only preflight from the build environment was blocked by the
"Production Reads" guard, so it is **unverified from the agent side** — the owner confirms it first,
step 1).

---

## 0. Never-bend rules that gate this procedure

1. **Upgrade only. Never run the `0009` downgrade on Supabase**, and never disable row security on
   any Supabase table (root `CLAUDE.md` rule 1). `0018`'s upgrade only *drops two RESTRICTIVE
   policies*; RLS stays `ENABLE`d with `chunk_source_read` + `chunk_labels_read` + the anon fences.
2. Migrating a live project is a **deliberate act with an explicit `DATABASE_URL`** — never
   `make migrate` (that is pinned to the local pgvector and cannot reach prod by design).
3. A **confirmed recent backup** of the Supabase project must exist before any upgrade.
4. Secrets never printed or pasted (rule 10). The prod `DATABASE_URL` comes from the host env / the
   root `.env`; do not echo it.

## 1. Prerequisites (owner)

- [ ] **Confirm the current prod revision yourself.** From `backend/` with the prod DSN in the
      environment: `uv run python scripts/setup_supabase.py preflight` — it prints the masked host,
      role, pgvector version, and `alembic : <version_num>`. Expected: `0014_chunk_scope_fail_closed`.
      If it is already ≥ `0016`, re-read this runbook — the per-migration notes still apply but some
      steps are no-ops (Alembic skips applied revisions).
- [ ] **Confirmed recent backup** of the Supabase project (point-in-time or a fresh snapshot).
- [ ] **Explicit go-ahead** recorded (the owner authorizes agent task 4, or runs it themselves).
- [ ] A maintenance expectation: ingestion should be quiesced during the upgrade (no webhook/sweep
      writing `labels` mid-migration). The live store is currently empty (0 chunks), so this is
      low-risk, but keep `ENABLE_BACKGROUND_JOBS=false` until the re-sync step.

## 2. The migration (0014 → head)

From `backend/`, with the **prod** `DATABASE_URL` exported in the shell (not committed, not echoed):

```
cd backend
DATABASE_URL="$PROD_DATABASE_URL" uv run alembic -c ../knowledge-base/migrations/alembic.ini upgrade head
```

This applies, in order, exactly the revisions not yet on prod:

| Rev | What it does | Isolation note |
|---|---|---|
| `0015_applicability` | adds the `applicability` column/plumbing | additive; no RLS change |
| `0016_chunk_labels` | adds `chunk.labels` + `page_source.labels` + partial GIN + the RESTRICTIVE `chunk_labels_read` policy (`app.allowed_labels`) | **adds** the routing-label fence; no-op until a connection sets the GUC |
| `0017_chat_session` | adds the `chat_session` table (writer-only, RLS ENABLEd, no policy) | adds an anon-fenced table; loosens nothing |
| `0018_retire_knowledge_scope_rls` | **drops** `chunk_scope_read` + `curated_knowledge_entry_scope_read` (the retired knowledge-scope axis) | RLS stays enabled; `chunk_source_read` (source/company isolation) + `chunk_labels_read` (routing) remain; re-exposes nothing to anon |

All four are additive-or-policy-only and carry downgrades. `0018` is the sanctioned, deliberate drop
(fix-forward, ADR-routing-labels-sole-content-axis); it is **not** a `0009`/`0010`/`0014`-style isolation downgrade.

## 3. Post-migration verification (before any re-sync)

- [ ] `uv run python scripts/setup_supabase.py preflight` → `alembic : 0018_retire_knowledge_scope_rls`.
- [ ] Confirm the isolation fence is intact and the scope axis is gone. As the DB owner (read-only):
      ```sql
      SELECT policyname, permissive FROM pg_policies WHERE tablename = 'chunk' ORDER BY policyname;
      ```
      Expect **`chunk_source_read` (PERMISSIVE)** and **`chunk_labels_read` (RESTRICTIVE)** present,
      and **`chunk_scope_read` ABSENT**. Likewise `curated_knowledge_entry_scope_read` absent on
      `curated_knowledge_entry` (its PERMISSIVE `*_reader_read` policy stays).
- [ ] `scripts/setup_supabase.py check-deploy-readiness` (counts; store is expected empty = 0 chunks
      until the re-sync).

## 4. Deploy the Path B backend

Deploy the backend image (Railway, per `railway-backend-deploy.md`) built from the Path B working
tree. On boot the backend now:
- loads `knowledge_scopes.json` = `classified`-only (no `-test` scopes), `knowledge_scope_set` empty;
- the scope filter is inert (GUC opted out) — retrieval routes on `chunk_labels_read` only;
- ingestion membership = routing labels (`ProductCatalog.all_routing_labels()`).
Confirm `GET /health` returns `knowledge_scopes: []` (empty, classified excluded) and the service
is healthy.

## 5. Re-sync + index the first batch (the nine routing-labelled pages)

- [ ] With the owner's nine routing-labelled pages present in Confluence (each carrying ≥1 routing
      label — `routing-test-labels.md`), run a reconciliation sweep so they index under the new
      membership rule: `uv run python scripts/run_reconciliation_once.py` (or enable
      `ENABLE_BACKGROUND_JOBS=true` and let the webhook/sweep run). A page needs **no**
      `obi-general-test` tag now — a routing label alone makes it a member.
- [ ] `check-deploy-readiness` → chunk count > 0; `scripts/page_state.py <page_id>` per page to
      confirm active chunks carry the expected `labels`.

## 6. Verify retrieval routing + isolation (agent task 4 proof)

- [ ] Run the live isolation check against the deployed store:
      `uv run python scripts/verify_directed_routing_live.py --mirror` (reader DSN = `rag_reader`, so
      the RLS policies bite). Expect: a `toast → mews` connection sees `obi-general` / `toast-general`
      / `mews-general` / `toast-to-pms` and **hides** `mews-to-pos` / `toast-to-accounting`; the
      `--mirror` reversed connection flips the direction box; `RESULT: PASS`, exit 0.
- [ ] Spot-check a real chat per the live-test runbook (`directed-routing-live-test.md`): the
      answer cites only pages in the connection's four boxes.

## 7. Rollback

- **Undo `0018` only (restore the scope axis), safe on any host:**
  ```
  DATABASE_URL="$PROD_DATABASE_URL" uv run alembic -c ../knowledge-base/migrations/alembic.ini downgrade -1
  ```
  `0018`'s downgrade **re-applies** `chunk_scope_read` + `curated_knowledge_entry_scope_read`
  (tightening — adds restriction back), so it never loosens isolation. Pair it with redeploying the
  pre-Path-B backend image (the one that sets the scope GUC), or retrieval will deny scope-tagged
  rows (the re-added policy is fail-closed on an unset scope GUC).
- **Do NOT downgrade below `0017`/`0016` on Supabase without re-reading the guards:** `0014`'s and
  `0010`'s downgrades are deliberately **blocked on Supabase** (they would drop isolation policies and
  re-expose the corpus). Prefer **fix-forward** over a deep rollback. The store being empty makes a
  full teardown-and-rebuild the cleanest recovery if ever needed.
- Backup restore (step 1) is the last resort for data loss, not for a policy change.

---

**Cross-references:** ADR-routing-labels-sole-content-axis (`docs/adr/routing-labels-sole-content-axis.md`), migration
`0018_retire_knowledge_scope_rls.py`, `supabase-vector-store-cutover.md`,
`deploy-readiness-scope-rls.md`, `directed-routing-live-test.md`, and the Path B status +
task list in `docs/Final_docs/sync-rules/plan.md`.
