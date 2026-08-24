# Phase 6 — Supabase vector store migration & deploy (ingestion-side impact)

**Status:** ⬜ **todo, deliberately deferred.** No code has been written for this phase. Everything
below is what `PLAN.md` (lines 3153–3216) specifies will happen, not what exists today — nothing
here should be treated as shipped.

## Files & folders that will be touched

```
apps/automation/app/platform/config/settings.py     DATABASE_URL / DATABASE_READER_URL
apps/automation/app/platform/db/engine.py            get_engine()/get_sessionmaker() (writer path)
apps/automation/alembic/                              alembic upgrade head against Supabase
infra/foundation/docker-compose.yml                   local dev stays on Docker pgvector, unaffected
docs/runbooks/                                         new: pooler caveats, backup/restore, rollback
```

## What this phase is

Moving the corpus + retrieval from local Docker pgvector to **Supabase** (managed Postgres +
pgvector) as the production vector store, while preserving the ADR-0004 source-isolation model
(see [phase-0.md](./phase-0.md), [phase-3.5.md](./phase-3.5.md)). Deploy/infra work only,
deliberately separated from Phase 5's accuracy/optimization work so neither blocks the other. Dev
stays on local Docker pgvector until this phase actually starts — moving dev onto a networked
Supabase instance ahead of a concrete ship date would trade a hermetic, zero-network test DB for a
networked dependency in every test loop, for no present benefit (`PLAN.md`'s own proportionality-
gate reasoning, root `CLAUDE.md`'s gate).

## What changes for ingestion specifically, once this phase starts

- **`DATABASE_URL`** (the writer connection every ingestion write already uses — worker, webhook,
  reconcile, `versioning.py`'s activation point) gets repointed at Supabase. The app talks to
  Postgres directly via `psycopg`, not Supabase's REST/JS SDK, so `ANON_KEY`/`SERVICE_ROLE_KEY` are
  never needed — only the Postgres connection string.
- **Role recreation.** Supabase manages roles differently (`authenticated`/`service_role`/`anon`,
  JWT-claim RLS, no plain superuser) — the docker init SQL that creates `rag_writer`
  (`BYPASSRLS`)/`rag_reader` locally won't run there; it has to be reapplied via a one-off script or
  a Supabase migration. The writer must retain a `BYPASSRLS`-equivalent path so ingestion's write
  behavior is unchanged.
- **pgvector ≥0.8 confirmation** — required for `hnsw.iterative_scan` (the RLS-scope recall safety
  valve from Phase 3.5.1); Supabase may pin an older version, which would need a mitigation decided
  before shipping.
- **Corpus load** — either re-embed via the existing version-stamp reuse gate
  ([phase-2.md](./phase-2.md#5-incremental-re-embedding-domainchunk_diffpy-versioningpy_resolve_children))
  or migrate rows directly.

## Blocked on the user (per `PLAN.md`, never invent these)

1. The connection string — session-pooler or direct, port 5432 (not the `:6543` transaction
   pooler, so Alembic migrations + prepared statements work), `postgresql+psycopg://` prefix.
2. Confirmation the Supabase instance runs pgvector ≥0.8.
3. How `rag_reader` + RLS map onto Supabase's role model.

## Not this file

- The RLS policy, reader-role scoping logic, and eval/isolation re-verification against Supabase
  once this phase runs — `../retrieval/phase-6.md`.
