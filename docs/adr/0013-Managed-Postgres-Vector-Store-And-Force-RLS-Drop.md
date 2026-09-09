# 0013 — Production Vector Store = Managed Postgres (Supabase on AWS), and Dropping FORCE on chunk RLS

Status: Accepted
Date: 2026-09-09
Governs: apps/automation (platform/db, alembic, retrieval, ingestion), infra/foundation, docs/runbooks
Relates to: ADR-0001 (Postgres+pgvector stack), ADR-0004 (source-keyed RLS isolation — preserved, not replaced)

## Context

The production corpus needs a hosted home. The engine is settled and is **not** being reconsidered:
ADR-0001 fixes the stack as Postgres + pgvector + tsvector, ADR-0002 builds retrieval on pgvector HNSW +
tsvector GIN + RRF, and ADR-0004 makes Postgres Row-Level Security the isolation spine. Every
requirement (dense, keyword, RLS, ACL, versioning, provider tags, job queue, `query_trace`, curated
knowledge) lives in one Postgres store; the docs explicitly rule out switching engines. What was still
open is only the **host** for that Postgres instance.

Two honest limits on this decision, recorded so they are not overstated: the docs commit to pgvector
positively but never benchmarked it head-to-head against Pinecone/Weaviate/Qdrant (those names appear
nowhere), and **no scale / latency / QPS / SLA target exists anywhere** (corpus today ≈ 9 pages / 85
chunks; latency is unmeasured until Phase 5.4). This choice is therefore validated against the stated
functional requirements, not against a future scale requirement that has not been written down. If such
a requirement lands, the host is a new decision, not a silently-assumed one.

A blocking implementation fact forces a companion change. `chunk` is created under **`FORCE ROW LEVEL
SECURITY`** (`platform/db/schema.py`), where *even the table owner* is subject to the default-deny
policy. On the local cluster the writer (`rag`) escapes it **only by being a SUPERUSER** — ownership
alone is not enough under `FORCE`. **No managed Postgres grants a true superuser** (Supabase's `postgres`
role is not one; neither is RDS's master role). So on cutover the writer/owner would be filtered to zero
rows by its own policy, and every ingestion / reconciliation read would silently return nothing. This is
independent of which managed host is chosen — it must be fixed on either.

## Decision

**D1 — Host.** Production vector store is **Supabase Cloud, provisioned in an AWS region** (managed
Postgres + pgvector). **AWS RDS/Aurora is kept as a documented, reversible fallback**, not the primary.
The requirement "part of our AWS ecosystem" is satisfied by **"hosted on AWS infrastructure and reachable
by connection string,"** not "inside our own AWS account/VPC/IAM"; Supabase Cloud already runs on AWS and
meets that with the least work.

**D2 — No lock-in.** The app stays plain-Postgres-over-`psycopg`: a DSN only, no Supabase REST/JS SDK, no
`ANON_KEY`/`SERVICE_ROLE_KEY`. Supabase → RDS/Aurora, if an in-VPC requirement ever hardens, is a
connection-string swap plus a role/RLS re-apply, not a rewrite.

**D3 — Connection shape.** Connect via the **session-pooler / direct port 5432**
(`postgresql+psycopg://…`), never the `:6543` transaction pooler (it does not hold session state that
`SET LOCAL app.allowed_sources` and other per-transaction GUCs depend on). Confirm **pgvector ≥ 0.8** on
the instance before cutover.

**D4 — Drop FORCE on `chunk` RLS.** Keep RLS **`ENABLE`d**; **drop `FORCE`**. A non-superuser *owner*
(the writer) is then exempt by ownership alone, while the non-owner `rag_reader` role stays fully
policy-bound. Landed as: `apply_chunk_rls` no longer issues `FORCE` (and asserts `NO FORCE` so a
pre-ADR-0013 database is corrected when the idempotent helper reruns), plus migration
`0008_drop_force_rls` (`ALTER TABLE chunk NO FORCE ROW LEVEL SECURITY`; downgrade re-`FORCE`s). The
writer must **own** `chunk` on the managed instance (tables created by the writer role via `alembic
upgrade`), and `rag_reader` remains a non-owner `NOSUPERUSER NOBYPASSRLS` login.

## Reason

`FORCE` only ever constrained the **owner**; read-path isolation was never carried by `FORCE`. Isolation
is enforced entirely by `rag_reader` being a **non-owner** role that cannot bypass RLS and is filtered by
the `chunk_source_read` policy against the per-transaction `app.allowed_sources` GUC. Removing `FORCE`
therefore lets the writer read its own rows without SUPERUSER (the thing managed Postgres cannot give)
**without changing what the reader can see** — ADR-0004's guarantee is preserved intact. Supabase-on-AWS
is chosen over going straight to RDS because it satisfies the stated requirement with the least work and
zero lock-in, keeping the eventual in-VPC move fully reversible.

## Consequences

- The writer/owner reads all rows on any managed instance without SUPERUSER; ingestion and
  reconciliation work on Supabase/RDS. Proven by `test_force_rls_managed_postgres.py`, which reproduces
  the condition by making a **non-superuser role own `chunk`** and asserting it can read (fails under the
  old `FORCE` code, passes after), alongside an assertion that the non-owner reader stays isolated.
- Read-path isolation (ADR-0004) is unchanged: the existing reader-isolation and permission-no-leak tests
  remain green.
- **Orthogonal and still open:** this does **not** address the customer-axis fail-open finding
  (`mews/opera/toast/general` enforced only by an app-layer predicate, no RLS on the customer axis) —
  that is Phase 11.1a and must be closed before any public deploy. ADR-0013 concerns the writer/owner
  bypass only.
- Downgrading `0008` re-`FORCE`s `chunk`, which again requires a SUPERUSER writer — i.e. it is only safe
  on the local cluster, not on managed Postgres. Recorded in the migration's docstring.

## Alternatives considered

- **Keep `FORCE`, grant the writer `BYPASSRLS`.** Managed Postgres does not reliably grant `BYPASSRLS` to
  the tenant role either, and it is a blunter, cluster-wide exemption than "owner of this one table." The
  ownership-based bypass is narrower and needs no special attribute.
- **Go straight to RDS/Aurora, skip Supabase.** Rejected as primary: more setup for no gain under the
  confirmed "on AWS + reachable" requirement, while the DSN-only design keeps RDS a cheap fallback.
- **Run retrieval as the owner and drop the reader role.** Rejected: it collapses the isolation boundary
  ADR-0004 exists to enforce. The non-owner reader is the entire mechanism and stays.

## Paths governed

- `apps/automation/app/platform/db/schema.py` — `apply_chunk_rls` (ENABLE, no FORCE)
- `apps/automation/alembic/versions/0008_drop_force_rls.py`
- `apps/automation/app/features/confluence_sync/tests/test_force_rls_managed_postgres.py`
- `infra/foundation/init/01-roles.sql`, `docs/runbooks/` (managed-Postgres cutover runbook, Phase 6)
