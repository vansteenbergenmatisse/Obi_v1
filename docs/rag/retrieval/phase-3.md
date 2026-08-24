# Phase 3 — Retrieval core (the original hybrid retriever)

**Status:** ✅ done, pre-dates `docs/rag/PLAN.md`'s detailed task list — `PLAN.md` itself picks up at
Phase 0/3.5 and refers back to this as "offline-verified through Phase 3: 99 tests green" (`PLAN.md`
line 1734). This file describes the original shape of the pipeline; [phase-3.5.md](./phase-3.5.md) and
[phase-4.md](./phase-4.md) describe everything added on top of it since.

## What happened

The original `HybridRetriever` (`app/features/retrieval/application/retriever.py`) shipped the core
retrieval algorithm still in use today:

1. **Dense search** — cosine distance over an HNSW index on `chunk.embedding`.
2. **Keyword search** — `ts_rank` over a GIN index on `chunk.tsv`.
3. **Reciprocal Rank Fusion** (`domain/fusion.py`) — `score = Σ 1/(k0 + rank)`, rank-based so it's
   robust to the two retrievers' different score scales.
4. **A baseline permission filter** (`domain/permission.py`) — `PrincipalPermissionPolicy.allowed()`,
   deciding page visibility from plain injected data (`space_of`, `restrictions`).
5. Both entry points — `retrieve()` (page ids only, the eval harness's `RankFn` shape) and the richer
   context-carrying variant — share one internal search core.

**What this phase did NOT have** (all added later, see [phase-3.5.md](./phase-3.5.md) and
[phase-4.md](./phase-4.md)):

- No reranker — RRF's fused order was final.
- No real, DB-backed principal ACL — `PrincipalPermissionPolicy` was built from fixture-fed data, not
  live `page_restriction` rows (that's Phase 4.3).
- No RLS-backed source isolation, no `rag_reader` role (that's Phase 3.5.3, ADR-0004).
- No `query_trace` scoreboard (that's Phase 3.5.4).
- No answer runtime on top — retrieval returned ranked page ids for the eval harness to score, nothing
  consumed it as a chatbot yet (that's Phase 4, `rag_agent`).

The current, extended state of every one of these files is documented alongside the later phases that
changed them — this file is the "what did Phase 3 itself ship" anchor, not the current behavior.

## Files & folders used

- `app/features/retrieval/application/retriever.py` — `HybridRetriever`, the original `retrieve()`
  entry point (still the eval harness's `RankFn` shape today).
- `app/features/retrieval/domain/fusion.py` — `reciprocal_rank_fusion` (unchanged since Phase 3).
- `app/features/retrieval/domain/permission.py` — `PrincipalPermissionPolicy` (signature since
  extended at Phase 4.6.6, see [phase-4.6.md](./phase-4.6.md); the live-DB wiring is Phase 4.3, see
  [phase-4.md](./phase-4.md)).
- `app/features/retrieval/infrastructure/search_repo.py` — `dense_search`, `keyword_search` (the
  reranker/text-fetch/scope additions are Phase 3.5.2/3.5.3, see [phase-3.5.md](./phase-3.5.md)).
- `app/features/evaluation/` — `runner.py`'s `evaluate(dataset, rank_fn, ...)`, the injected-ranker
  harness this phase's `retrieve()` shape was built to satisfy.
- `apps/automation/tests/fixtures/confluence/` — the fixture corpus retrieval is measured against
  offline (no live Confluence needed).

See [`../how_this_works.md`](../how_this_works.md) §7.1 and §9 for the full pipeline diagram and a
worked example against fixture page 1001.
