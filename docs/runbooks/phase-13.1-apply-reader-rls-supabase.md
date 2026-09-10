# Phase 13.1 — apply the reader-RLS fix (migration 0009) to Supabase

> ## ✅ COMPLETED on the current Supabase project (2026-09-09)
> Migration `0009` **is applied** — live alembic head is `0009_reconcile_non_chunk_rls`, the three
> `*_reader_read` policies exist, and `rag_reader` reads `page_source`/`page_restriction`/
> `curated_knowledge_entry` while `anon`/`authenticated` stay default-denied. **Do not re-run** the
> apply steps against the current project. This runbook is retained as the procedure for a **fresh
> Supabase deploy** (where the head starts below `0009`).

**What this is:** the exact steps to fix a reader lockout on Supabase, safely — RLS is enabled on the
non-`chunk` tables with no policy for `rag_reader`, so the reader reads 0 rows until `0009` adds its
role-scoped policies. Run these on any **fresh** Supabase project whose alembic head is below `0009`.

**Snapshot from the read-only introspection that motivated this (2026-09-09, now HISTORICAL — the
current project is at `0009`):**
- alembic head = `0008_drop_force_rls` → **0009 not yet applied** (at that time).
- All 12 tables have RLS **enabled**; only one policy exists (`chunk_source_read`).
- `anon` **and** `authenticated` (Supabase's public REST roles) hold `GRANT SELECT` on **every**
  table.

---

## Read this first — why you must NOT just "disable RLS"

You said you didn't enable RLS. You (or Supabase's defaults) ended up with RLS enabled on every
public table, and **that is currently the only thing keeping your data private.** On Supabase the
`anon` role is the *unauthenticated public* role behind the auto-generated REST API
(`https://<project>.supabase.co/rest/v1/<table>`). It has `SELECT` on all your tables. With RLS
enabled and no policy for `anon`, it reads **0 rows** — safe.

**If you disable RLS, `anon` can read every row of every table over the public internet, no auth.**
That includes the whole Confluence corpus (`chunk`, `document`, `page_source`, …). So the fix is
*not* to disable RLS — it's to **keep RLS on** and add a policy that lets **only** the `rag_reader`
retrieval role back in. That is exactly what migration 0009 now does.

(Your `rag_reader` role connects via direct Postgres, not the REST API, so a role-scoped policy lets
it in without opening anything to `anon`.)

---

## What 0009 does

1. `enable_non_chunk_rls` — makes sure RLS is ON for every non-`chunk` table (already true on your
   store; this makes a *fresh* deploy safe too — `anon` stays locked out by default).
2. `apply_reader_rls` — adds a `FOR SELECT TO rag_reader USING (true)` policy to the three tables
   retrieval actually reads: `page_source`, `page_restriction`, `curated_knowledge_entry`. Only
   `rag_reader` matches it; `anon`/`authenticated` stay default-denied.
3. `chunk` is left exactly as-is (its stricter source-scoped policy still applies).

Net effect on live: retrieval's page ACL and curated layer start working through `rag_reader`, and
**nothing new becomes visible to `anon`.**

---

## Do this — Option 1 (recommended): apply via alembic

Your `.env` `DATABASE_URL` currently points at Supabase as the owner (`postgres`), which is what
alembic needs. From `apps/automation`:

```bash
# 1. Confirm you're pointed at Supabase and see the current head
uv run alembic current          # a fresh deploy shows a head below 0009 (e.g. 0008_drop_force_rls).
                                # The current live project is already 0009 — nothing to do there.

# 2. Apply 0009 (creates the reader policies; rag_reader already exists on your store)
uv run alembic upgrade head

# 3. Confirm
uv run alembic current          # expect: 0009_reconcile_non_chunk_rls
```

That's it. Because `rag_reader` already exists on your project, step 2 creates the three reader
policies immediately.

> ⚠️ Test-suite note (unchanged): while `.env` points at Supabase, run the pytest suite with a local
> override — `DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag
> DATABASE_READER_URL="" uv run pytest -q`. `alembic upgrade head` above is the one thing you *do*
> want to run against Supabase.

## Do this — Option 2 (manual, Supabase SQL editor)

If you'd rather run SQL directly (Supabase → SQL editor), this is the equivalent of 0009. It's
idempotent:

```sql
-- keep anon/authenticated out (already true on your store; harmless to re-assert)
alter table page_source            enable row level security;
alter table page_restriction       enable row level security;
alter table curated_knowledge_entry enable row level security;

-- let ONLY rag_reader read these three tables
drop policy if exists page_source_reader_read            on page_source;
create policy page_source_reader_read            on page_source            for select to rag_reader using (true);

drop policy if exists page_restriction_reader_read       on page_restriction;
create policy page_restriction_reader_read       on page_restriction       for select to rag_reader using (true);

drop policy if exists curated_knowledge_entry_reader_read on curated_knowledge_entry;
create policy curated_knowledge_entry_reader_read on curated_knowledge_entry for select to rag_reader using (true);
```

If you take Option 2, still run `uv run alembic stamp 0009_reconcile_non_chunk_rls` afterward so the
repo and the DB agree on the head. (Prefer Option 1 to avoid this.)

---

## Verify it worked

In the Supabase SQL editor:

```sql
-- 1. The three reader policies exist, scoped to rag_reader
select tablename, policyname, roles, cmd
from pg_policies
where policyname like '%_reader_read'
order by tablename;
-- expect 3 rows, roles = {rag_reader}

-- 2. RLS still ON everywhere (anon still fenced out)
select relname, relrowsecurity
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and relkind = 'r'
order by relname;
-- expect relrowsecurity = true for all tables
```

Then a real end-to-end check: ask the widget a question and confirm you get grounded, cited answers
(the reader can now read `page_source`/`page_restriction` for the ACL step). If you later seed
curated knowledge, confirm those entries show up in answers.

---

## Rollback

```bash
uv run alembic downgrade 0008_drop_force_rls
```

⚠️ **Do not run the downgrade against Supabase.** Its downgrade disables RLS on the non-`chunk`
tables, which would re-expose them to the public `anon` REST role. The downgrade is only for a store
with no PostgREST/`anon` exposure (local docker, or an RDS/Aurora fallback). To reverse on Supabase,
instead just drop the three `*_reader_read` policies (the reader goes back to locked-out, but nothing
is exposed).

---

## Follow-ups (tracked in PLAN.md Phase 13)

- **13.2 — ✅ DONE (`ec7c372`).** `scripts/setup_supabase.py` `provision-reader` now calls
  `apply_reader_rls` after creating the role (so a *fresh* deploy, which migrates before the role
  exists, still gets the policies), and `verify-isolation` checks that `rag_reader` can read
  `page_source` / `page_restriction` / `curated_knowledge_entry` while an `anon`-like role cannot.
- **13.3 — ✅ DONE.** Doc sweep: the docs that said curated / non-`chunk` tables "have no RLS" (now
  false), the FORCE-RLS note (resolved by `0008`), the table count, and the alembic head are corrected.
- **11.1a** — the customer-scope (mews/opera/toast) fail-closed backstop is a *separate* axis and
  still outstanding before any public deploy.
