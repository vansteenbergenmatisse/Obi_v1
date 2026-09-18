# Phase 6 — Supabase vector store migration (retrieval-side impact)

**Status:** 🟩 live cutover done + verified against Supabase (2026-09-09); production traffic NOT
switched, work UNCOMMITTED — operator decides commit + go-live. The write-path/infra half (repointing
`DATABASE_URL`, the FORCE-RLS drop, corpus load, role recreation) is in
[`../ingestion/phase-6.md`](../ingestion/phase-6.md); this file covers only what the move means for
the read/answer path and how it was re-verified live.

## What changes for retrieval

Nothing in retrieval *code* changes — the whole point of ADR-0001/0002/0004 is that the store is
plain Postgres + pgvector + RLS behind a DSN. The move is:

- **Reader connection repointed.** The RLS-scoped reader engine (`DATABASE_READER_URL`,
  `platform/db/engine.py::get_reader_engine`/`get_reader_sessionmaker`) now points at the managed
  instance as the non-owner `rag_reader` role. `provision-reader` derives this DSN and writes it to
  `.env` — the pooler username is `rag_reader.<project_ref>`.
- **RLS is the same policy on a host with no superuser.** Under ADR-0013 the writer/owner is exempt
  by *table ownership + `NO FORCE`* (not superuser/`BYPASSRLS`), while `rag_reader` stays policy-bound
  by `chunk_source_read`. The read-path guarantee of [phase-0.md](./phase-0.md) /
  [phase-3.5.md](./phase-3.5.md) — default-deny, scoped by `app.allowed_sources` — is unchanged.
- **pgvector ≥ 0.8 confirmed live (0.8.2).** Required for `hnsw.iterative_scan`, the RLS-scope recall
  safety valve from [3.5.1](./phase-3.5.md#351--pin-pgvector--08--enable-hnsw-iterative-scan).

## How the read path was re-verified against Supabase

- **Isolation (`scripts/setup_supabase.py verify-isolation`, live):** owner sees **85** chunks;
  `rag_reader` with **no** `app.allowed_sources` GUC → **0** (default-deny); scoped to the real source
  → **85**; scoped to a bogus source → **0**. This is the ADR-0004 read-path contract, proven on the
  real instance — and it also proves `rag_reader` authenticates through the session pooler.
- **Retrieval quality (`make eval`, live):** retrieval_smoke recall@5 **1.000** / mrr 0.750 /
  hit_rate@5 1.000; ambiguity recall@5 1.000; permission recall@5 0.667; out_of_corpus 0.000
  (correct — nothing to retrieve). Full hybrid path (pgvector dense + tsvector keyword + RRF + Cohere
  rerank) works end-to-end on the managed store.
- **Cross-provider exclusion is NOT live-demonstrable.** The whole corpus is `general` (single source
  `confluence:default`), so "Mews-scoped can't retrieve Toast-only" has no real data to show. It stays
  proven by `app/features/confluence_sync/tests/test_retrieval_knowledge_scope.py`, which stamps
  synthetic mews/toast tags and asserts structural exclusion (24 isolation tests pass against the
  local superuser docker; the suite can't provision roles on managed Postgres — see the runbook).

## Not this file

- The write-path move (DSN repoint, FORCE-RLS drop + migration `0008`, `rag_reader` provisioning,
  corpus dump/restore, FK-ordering caveats) — [`../ingestion/phase-6.md`](../ingestion/phase-6.md).
- The step-by-step operator procedure + recorded results —
  [`../../runbooks/supabase-vector-store-cutover.md`](../../runbooks/supabase-vector-store-cutover.md).
