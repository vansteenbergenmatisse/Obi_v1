# Phase 6 — Supabase vector store migration & deploy (ingestion-side impact)

**Status:** 🟩 **live cutover done + verified against Supabase (2026-09-09); production traffic NOT
switched, work UNCOMMITTED — operator decides commit + go-live.** The prerequisite RLS fix
(**ADR-0013** + migration `0008_drop_force_rls` + `apply_chunk_rls`, TDD-gated by
`app/features/confluence_sync/tests/test_force_rls_managed_postgres.py`) landed first, then the full
cutover ran green on Supabase (project `vtpbwkbbkfukfmytlqns`, `eu-west-1`, session pooler `:5432`):
preflight (pgvector 0.8.2, owner `is_superuser=off`) → `alembic upgrade head` (`0008`, `chunk`
`rowsecurity=t forcerowsecurity=f`) → `provision-reader` (`rag_reader.<ref>`, `DATABASE_READER_URL`
written to `.env`) → corpus load (9/9/9/85/9, single source `confluence:default`) → parity
(`verify-isolation` owner 85 / reader-no-GUC 0 / scoped 85 / bogus 0; `make eval` retrieval_smoke
recall@5 1.000). Full procedure + recorded results: **`docs/runbooks/supabase-vector-store-cutover.md`**.
See `PLAN.md` §0 (2026-09-09) for the ledger entry and the remaining operator decisions (commit;
Phase 11.1a before any public deploy; one-line DSN rollback to local).

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
  JWT-claim RLS, **no plain superuser and no reliable `BYPASSRLS` for the tenant role**) — the docker
  init SQL that creates `rag_reader` locally won't run there; it has to be reapplied via a one-off
  script or a Supabase migration. **How the writer bypasses RLS changed (ADR-0013):** it is no
  longer via superuser/`BYPASSRLS` but via **table ownership with `FORCE` dropped** — the writer
  role must *own* `chunk` (i.e. create the tables through `alembic upgrade` as that role), after
  which `ENABLE`d-but-not-`FORCE`d RLS exempts the owner while `rag_reader` stays policy-bound. This
  is what makes ingestion writes work on a host with no superuser; the reader isolation is unchanged.
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
