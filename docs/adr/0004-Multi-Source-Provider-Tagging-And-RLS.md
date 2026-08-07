# 0004 — Multi-Source Provider Tagging and Row-Level Security

Status: Accepted
Date: 2026-08-07
Governs: apps/automation (retrieval, ingestion, platform/db, alembic), infra/foundation

## Context

One backend and one corpus must power *many* chatbots, each scoped to a subset of **source systems** (a
"provider": Confluence today; Zendesk / Notion / uploads later), with a **hard security boundary** between
scopes and **default-deny**. The as-built schema has no source/tenant column — only Confluence `space_id`
(`models.py:91,231`) — so nothing today can isolate whole source systems. Confluence is the only source
for now, so we add the isolation spine without generalizing the Confluence-specific ingestion or gateway
yet. This ADR fixes the isolation model; the reranker/answer pipeline is ADR-0005.

## Decision

1. **Provider-tag columns on `page_source` and `chunk` only** (retrieval never reads `document_version`):
   `source_type String(32)` (coarse connector label), `source_id String(128)` (the isolation key, e.g.
   `confluence:default`), `tags ARRAY(Text)` (free-form per-source tags for bot scoping). `source_type`
   is a **CHECK constraint, not a PG enum** — new connectors must not require `ALTER TYPE`.

2. **Two layered controls, both always applied on every read.** Source-level **RLS** on `chunk` isolates
   whole source systems; page-level **principal ACL** (persisted in Phase 4, ADR-0005 territory) enforces
   per-page read restrictions within a source. They are distinct layers; neither replaces the other.

3. **Postgres RLS keyed by `source_id`, default-deny.**
   ```sql
   ALTER TABLE chunk ENABLE ROW LEVEL SECURITY;
   ALTER TABLE chunk FORCE  ROW LEVEL SECURITY;
   CREATE POLICY chunk_source_read ON chunk FOR SELECT
     USING (source_id = ANY(string_to_array(current_setting('app.allowed_sources', true), ',')));
   ```
   An unset GUC yields `NULL` → `string_to_array(NULL,',')` → `= ANY(NULL)` is never true → **zero rows**.
   A retrieval that forgets to set the scope leaks nothing.

4. **Role split.** `rag_writer` (owner, `BYPASSRLS`) runs the write path — worker, webhook, reconcile,
   ingestion, and `query_trace` inserts — untouched by RLS. `rag_reader` (login, **non-owner**, no
   `BYPASSRLS`, `GRANT SELECT` on read tables) runs the read path. Because the owner bypasses RLS, reads
   **must** run as `rag_reader`. `engine.py` adds `get_reader_engine()`/`get_reader_sessionmaker()` bound
   to `database_reader_url` (falls back to `database_url` if empty).

5. **Scope is bound as a parameter with `set_config`, never `SET LOCAL`.** `SET LOCAL` cannot bind a
   parameter; using it here would be either an injection vector or a silent default-deny. The retriever
   issues, per transaction: `SELECT set_config('app.allowed_sources', :s, true)`.

6. **Belt-and-suspenders recall.** `_base_filters()` also carries an explicit
   `AND source_id = ANY(:sources)`, and a new partial index `ix_chunk_active_source (is_active, source_id)
   WHERE is_active` lets the planner use the source index. RLS is the security net; the explicit `WHERE`
   is correctness + recall.

7. **pgvector ≥ 0.8 is a prerequisite, pinned first.** A narrow RLS predicate prunes the HNSW candidate
   set, so an ANN scan can return fewer than `LIMIT` rows. `hnsw.iterative_scan` (pgvector 0.8+) is the
   safety valve, set per transaction alongside the scope GUC (`relaxed_order`, acceptable because we
   re-rank downstream). The `pgvector/pgvector:pg16` rolling tag is pinned to a 0.8.x digest.

8. **One ingestion seam.** The single activation point in `ingestion/application/versioning.py` writes
   `source_id="confluence:default"` (+ `source_type`, `tags`) — a constant today, a parameter when a
   second source lands. The Confluence-specific ingestion/gateway is **not** generalized further yet.

9. **The migration is the first real migration** (`down_revision="0001_core_schema"`): add the three
   columns `NOT NULL` with a `server_default` (backfilling existing rows to `confluence:default` /
   `confluence` / `{}`), **then drop the default** so ingestion must set `source_id` explicitly; add the
   index, the CHECK constraint, and the RLS DDL. Reversible: `alembic downgrade -1` restores 0001 state.

10. **The eval harness ships in the same PR.** `test_retrieval_eval.py` builds the retriever as the writer
    today; switching retrieval to the non-owner reader makes it RLS-subject → 0 rows unless it sets
    `app.allowed_sources`. The RLS PR therefore also creates the `rag_reader` role in the test harness and
    adds a **negative isolation test** (wrong `source_id` → 0 rows; reader cannot see unscoped rows). RLS
    and its test never split across PRs.

## Reason

A security boundary the database enforces survives an application bug; a boundary enforced only in
application code fails the first time a query forgets to filter. Default-deny makes the failure mode "no
results," never "wrong tenant's results." Keeping the writer on `BYPASSRLS` leaves the verified write path
(ingestion, worker, reconcile) untouched while the read path gains real isolation. CHECK-over-enum and a
single ingestion seam keep the door open for the next source without an `ALTER TYPE` or a rewrite.

## Alternatives considered

- **Application-only source filtering (no RLS).** Rejected: a single missed `WHERE` leaks across the hard
  boundary. RLS makes the database the enforcer of last resort.
- **A PG enum for `source_type`.** Rejected: every new connector would need `ALTER TYPE ... ADD VALUE`,
  which does not run inside a transaction and complicates migrations. CHECK constraint instead.
- **Per-source tables / schemas / databases.** Rejected: many-sources-one-corpus with shared retrieval,
  fusion, and eval is the product requirement; physical separation would fork the whole pipeline.
- **`SET LOCAL` for the scope GUC.** Rejected: it cannot bind parameters — an injection vector or a silent
  default-deny. `set_config(..., true)` is parameter-safe.

## Consequences

- Retrieval must run as `rag_reader`; any read accidentally left on the owner connection silently bypasses
  RLS. The reader engine and its use in `HybridRetriever` are the guard.
- pgvector is now version-sensitive (≥ 0.8 pinned by digest); an image downgrade would remove the
  iterative-scan safety valve and could make RLS scopes under-return.
- Ingestion for a second source is a parameter change at one seam, not a schema change.

## Paths governed

`apps/automation/app/features/{retrieval,ingestion}/**`, `apps/automation/app/platform/db/**`,
`apps/automation/alembic/**`, `apps/automation/app/platform/config/settings.py`,
`infra/foundation/docker-compose.yml`, and the eval harness
(`confluence_sync/tests/conftest.py`, `test_retrieval_eval.py`).
