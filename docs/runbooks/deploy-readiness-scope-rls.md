# Deploy-readiness gate — customer-scope RLS (migration 0010)

**When:** before exposing Obi's reader path (the `/chat` retrieval read) on any real, non-local
database — Supabase staging or production. **Not needed for the local demo** (see below).

## What it protects

Migration `0010_customer_scope_rls` installs the RESTRICTIVE customer-scope RLS policies
(`chunk_scope_read` on `chunk`, `curated_knowledge_entry_scope_read` on `curated_knowledge_entry`)
that are Obi's fail-closed tenant backstop (ADR-0014): a read under an unset or wrong scope GUC
returns nothing, independent of the application flag. If the reader path is exposed on a database
where `0010` was never applied (head `< 0010`) or where a downgrade dropped the policies, that
backstop is silently absent and cross-integration isolation rests on the application layer alone.

## The gate

```
cd backend && DATABASE_URL=<target> uv run python scripts/setup_supabase.py check-deploy-readiness
```

Read-only (catalog SELECTs only; prints no secret — masked host + db name). It asserts, for both
scope policies: the table exists, the policy is present `AS RESTRICTIVE FOR SELECT`, and row
security is ENABLEd on the table. On any gap it prints what is missing and
`Do NOT expose the reader path until \`alembic upgrade head\` (>= 0010) is applied` and exits
non-zero (10). All-present exits 0. Wire it as a blocking step in the deploy pipeline before the
reader path is served.

Note it checks RLS **ENABLE**, not **FORCE**: ADR-0013 deliberately keeps `chunk` at `ENABLE` +
`NO FORCE` (owner-role exemption on managed Postgres); `ENABLE` is what binds the non-owner reader
role to the RESTRICTIVE policy, so requiring `FORCE` would contradict ADR-0013.

## Local demo: why it is inert, and still mandatory before deploy

`0010` runs unconditionally everywhere (`alembic upgrade head`), including local. Locally its RLS is
merely **inert**, because local reads use the RLS-exempt owner role — so the policies exist but do
not constrain the owner. That is expected: the local demo does not rely on DB-level tenant
isolation. Before any real deployment where a non-owner reader role serves `/chat`, `0010` is
**mandatory** and this gate must pass — it is the check that the backstop is actually in force for
the reader role, not just present in a migration file.

_Automated proof: `backend/app/features/confluence_sync/tests/test_deploy_readiness_check.py`
(gap MIG-02 / ADR-0014) — ready-when-present and fails-closed-when-absent, both rolled back._
