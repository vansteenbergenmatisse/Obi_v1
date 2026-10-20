# Deploy-readiness gate — source RLS backstop

**When:** before exposing Obi's reader path (the `/chat` retrieval read) on any real, non-local
database — Supabase staging or production. **Not needed for the local demo** (see below).

> The file name is historical. The knowledge-scope RLS policies this gate used to check
> (`chunk_scope_read`, `curated_knowledge_entry_scope_read`, migration `0010`) were dropped by
> migration `0018_retire_knowledge_scope_rls` (ADR-routing-labels-sole-content-axis). The gate now
> checks the source/company fence.

## What it protects

Obi's fail-closed tenant backstop is the PERMISSIVE source policy plus row security ENABLEd. A single
PERMISSIVE SELECT policy on an RLS-enabled table is deny-by-default: the non-owner `rag_reader` sees
only the rows it admits, and an unset `app.allowed_sources` admits none. If the reader path is
exposed on a database where these policies are missing or row security was disabled, source/company
isolation fails open (never-bend rule 1).

## The gate

```
cd backend && DATABASE_URL=<target> uv run python scripts/setup_supabase.py check-deploy-readiness
```

Read-only (catalog SELECTs only; prints no secret — masked host + db name). It asserts, for
`chunk.chunk_source_read` and `curated_knowledge_entry.curated_knowledge_entry_reader_read`: the table
exists, the policy is present as `PERMISSIVE FOR SELECT`, and row security is ENABLEd on the table.
It also reports whether the routing-label policy `chunk_labels_read` is present, but never fails on
it: that policy is RESTRICTIVE and fail-open by design (an unset `app.allowed_labels` opts out), so
its absence loses label routing, not tenant isolation. On any gap it prints what is missing, tells
you not to expose the reader path until `alembic upgrade head` and
`setup_supabase.py provision-reader` have run, and exits non-zero (10). All-present exits 0.

### Enforcement status: MANUAL today (CFG-G)

This gate is a **manual step today**. There is **no automated deploy pipeline yet**, so nothing
calls `check-deploy-readiness` automatically before the reader path is served — an operator MUST run
the command above by hand against the real target DSN before exposing `/chat` on any non-local
database, and refuse the deploy on a non-zero exit. Do not read the sentence below as a claim that
the gate is already enforced automatically; it is not.

**When a deploy mechanism exists, it MUST be wired in.** The check has to run as a **blocking
pre-serve step** in whatever deploys the reader path (the CD job / release workflow / container
entrypoint that promotes the retrieval service), against that environment's `DATABASE_URL`, and a
non-zero exit MUST abort the deploy before the reader role can serve a single `/chat` read. Until
that pipeline exists, this runbook — run by hand — is the gate.

**CI runs it only as a smoke test, not as the gate.** `.github/workflows/ci.yml` has a step
(`deploy-readiness check — smoke only`) that runs `check-deploy-readiness` against a freshly-migrated
**local** Postgres to prove the CLI itself works and the migrations still install the source backstop. That
is a regression canary against the local store; it is explicitly **not** the production gate and
says nothing about any real target database.

Note it checks RLS **ENABLE**, not **FORCE**: ADR-supabase-postgres-store-without-force-rls deliberately keeps `chunk` at `ENABLE` +
`NO FORCE` (owner-role exemption on managed Postgres); `ENABLE` is what binds the non-owner reader
role to the policy, so requiring `FORCE` would contradict ADR-supabase-postgres-store-without-force-rls.

## Local demo: why it is inert, and still mandatory before deploy

The migrations run unconditionally everywhere (`alembic upgrade head`), including local. Locally the
RLS is merely **inert**, because local reads use the RLS-exempt owner role — so the policies exist
but do not constrain the owner. That is expected: the local demo does not rely on DB-level tenant
isolation. Before any real deployment where a non-owner reader role serves `/chat`, this gate must
pass — it is the check that the backstop is actually in force for the reader role, not just present
in a migration file.

_Automated proof: `backend/app/features/confluence_sync/tests/test_deploy_readiness_check.py`
(gap MIG-02 / ADR-db-level-customer-scope-isolation-backstop) — ready-when-present and fails-closed-when-absent, both rolled back._
