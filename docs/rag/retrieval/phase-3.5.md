# Phase 3.5 — Accuracy + tagging spine (retrieval-relevant sub-steps)

**Status:** ✅ done (`docs/rag/PLAN.md` lines 1869–2069). Only the retrieval-relevant sub-steps are
covered here — **3.5.6** (Confluence source scoping, `source_scope` table) is entirely write-path and
is documented in [`../ingestion/phase-3.5.md`](../ingestion/phase-3.5.md); the writer/tagging half of
**3.5.3** (stamping `source_id` at ingestion) is there too.

## 3.5.1 — Pin pgvector ≥ 0.8 + enable HNSW iterative scan

pgvector 0.8.5 pinned by digest. `hnsw.iterative_scan` is set **per-transaction**, in the same
transaction as the search queries, so a narrow RLS/source scope doesn't silently under-return results
(the HNSW index can otherwise stop scanning before finding enough post-filter matches).

**Files:** `app/features/retrieval/infrastructure/search_repo.py::apply_hnsw_gucs` — validates
`ef_search` (coerced to `int`) and `iterative_scan` (whitelisted against `_ITERATIVE_SCAN_MODES =
{"off", "relaxed_order", "strict_order"}`) before interpolating into `SET LOCAL` (which cannot bind
parameters — the whitelist is what keeps this injection-safe). Called from
`HybridRetriever._search` (`application/retriever.py`) before every search.

## 3.5.2 — Cross-encoder reranker (Cohere / Fake)

The reranker client mirrors the embeddings-client abstraction (ADR-0005 decision 2):

- `app/platform/clients/reranker_client.py` — `Reranker` protocol (`model: str`,
  `rerank(query, docs, top_k) -> list[(page_id, score)]`), `CohereReranker` (`POST
  https://api.cohere.com/v2/rerank`, timeout/retry/breaker/abuse-cap discipline matching
  `_HttpEmbeddingProvider`), `FakeReranker` (identity — preserves input order, deterministic for
  tests/offline), `build_reranker(settings, client=None)` with offline fallback (empty key, provider
  `fake`, or an offline env → `FakeReranker`).
- `app/features/retrieval/infrastructure/search_repo.py::fetch_rerank_texts` — a `DISTINCT ON
  (page_id)` query fetching one representative child chunk's text per page, under the same
  `_base_filters` as search, so a page the pre-model filters would exclude is never reranked in.
- `app/features/retrieval/application/retriever.py::HybridRetriever._search` — reranks the permitted
  candidate set (`allowed[:rerank_depth]`) **after** the permission filter, never before (see 3.5's
  RLS/ACL note below).

Tests force `reranker_provider=fake` via the hermetic settings fixture, so CI stays deterministic
even though `.env` may carry a live Cohere key.

## 3.5.3 — RLS enforcement at query time (`rag_reader` role, default-deny)

The retrieval-side half of provider tagging + RLS (ADR-0004). The writer/tagging half — stamping
`source_id`/`tags` at ingestion — is in [`../ingestion/phase-3.5.md`](../ingestion/phase-3.5.md).

- **Non-owner `rag_reader` role** — retrieval reads through a role with no `BYPASSRLS`, unlike the
  writer path (`rag`, a superuser). `app/platform/db/engine.py::get_reader_engine()` builds the
  reader-role connection.
- **Default-deny GUC** — `app/features/retrieval/infrastructure/search_repo.py::apply_source_scope`
  sets `app.allowed_sources` via a **bound** parameter (`set_config(..., is_local=true)`) — never
  interpolated, since the caller's source list would otherwise be an injection vector. An empty list
  yields an empty string, which matches nothing → default-deny.
- **Explicit `source_id = ANY(:sources)` predicate alongside RLS** — `_base_filters` in
  `search_repo.py` adds this as the query's own predicate (correctness + planner-friendliness); RLS is
  the enforced security net underneath it, not the only line of defense.
- **Fails closed outside offline environments when misconfigured** — see
  [phase-4.6.md](./phase-4.6.md)'s 4.6.10 entry: `get_reader_engine()` raises
  `ReaderRoleMisconfiguredError` if `database_reader_url` is unset outside `local`/`test`/`dev`/`ci`.

## 3.5.4 — `query_trace` scoreboard

Every retrieval writes one `query_trace` row on a **separate WRITER session** (so RLS on the reader
session never blocks the insert): raw query, retrieved page/chunk ids, allowed sources, embedding +
reranker model, rerank scores, latency. Phase 4.2 later extends the same row with the answer runtime's
own columns (`rewritten_query`, `answer`, `citations`, `feedback`) via `UPDATE`, not a second row — see
[phase-4.md](./phase-4.md).

**Files:** `app/features/retrieval/infrastructure/trace_repo.py` (`write_query_trace`,
`update_query_trace_answer`, `update_query_trace_feedback`); `app/platform/db/models.py::QueryTrace`.

## 3.5.5 — Rerank-lift measurement + Phase 3.5 exit gate

`evaluation/metrics/retrieval_metrics.py` (recall@k, precision@k, MRR, NDCG@k, hit_rate@k) plus a new
`evaluate_rerank_lift` comparing before/after-rerank scores. Measured live against Cohere `rerank-v3.5`
+ OpenAI-3072: **ndcg@10 −0.123, precision@5 +0.000** on `retrieval_smoke` — the fixture is already
saturated (dense alone ranks the one relevant page first), so there's no headroom to show lift; the
real measurement is deferred to a Phase-5 gold-set (see [phase-5.md](./phase-5.md)).
`refusal_min_rerank_score = 0.10` was set provisionally here, re-tuned in Phase 5.

**Exit gate met:** `make check` green (120 tests at the time), `make eval` prints the before/after
rerank table, isolation tests pass (RLS default-deny + wrong-source → 0 rows), pgvector 0.8.5 pinned,
every retrieval writes one `query_trace` row.

## Files & folders used (this file's scope)

- `app/platform/clients/reranker_client.py`
- `app/features/retrieval/application/retriever.py`
- `app/features/retrieval/infrastructure/search_repo.py`
- `app/features/retrieval/infrastructure/trace_repo.py`
- `app/platform/db/engine.py` (`get_reader_engine`)
- `app/platform/db/models.py` (`QueryTrace`)
- `app/features/evaluation/metrics/retrieval_metrics.py`, `run_baseline.py`

See [`../ingestion/phase-3.5.md`](../ingestion/phase-3.5.md) for 3.5.3's writer/tagging half and 3.5.6
(source scoping).
