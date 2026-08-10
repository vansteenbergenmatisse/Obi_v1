# DESIGN — Omniboost RAG: accuracy-first, source-isolated retrieval + answer runtime

> The governing design document for the accuracy-first upgrade. It is **normative**: where it and a
> stray comment or a handover disagree, this doc (backed by an ADR) wins. It describes the as-built
> system with file anchors, the target pipeline stage by stage, the source-isolation security model,
> the accuracy stack, the tracing scoreboard, the config surface, and a keep/upgrade/add/reject
> verdict on every layer the market-research brief proposed.
>
> Companion reading: [`how_this_works.md`](./how_this_works.md) is the A-to-Z *explainer* of the
> as-built system; [`PLAN.md`](./PLAN.md) is the *execution* plan (tasks, DDL, acceptance checks).
> This doc is the *design of record* those two hang off. Decisions here are ratified in
> [`../adr/0004-Multi-Source-Provider-Tagging-And-RLS.md`](../adr/0004-Multi-Source-Provider-Tagging-And-RLS.md)
> and [`../adr/0005-Reranking-And-Answer-Pipeline.md`](../adr/0005-Reranking-And-Answer-Pipeline.md).
>
> `TODAY` = shipped and verified. As of 2026-08-10 that is **Phases 1–3 + all of Phase 3.5** (reranker,
> provider tags + RLS + reader role, `query_trace`, rerank-lift eval, Confluence source scoping),
> **all of Phase 4** — the `rag_agent` DTO contract + domain core, the full `AnswerService` answer
> workflow (rewrite → retrieve/rerank → CRAG retry → refusal → parent expansion → grounded generation
> → citation enforcement), real, persisted principal ACL storage (`page_restriction`, replacing the
> fixture-fed policy), a live, secured `POST /chat` SSE endpoint + `PATCH /chat/{trace_id}/feedback`,
> and the web chat UI (`apps/web/src/features/chat`, live-verified end to end in a browser) — **and
> Phase 5.1**, the `CHAT_API_KEY` rotation mechanism (dual-key overlap window, `scripts/
> rotate_chat_api_key.py`, `docs/runbooks/chat-api-key-rotation.md`) — **and Phase 5.2**, an
> in-process exact-match answer cache (`CachingAnswerService`, `app.shared.ttl_cache.TTLCache`) —
> **213 backend tests green** (plus 39 `apps/web` vitest tests, its first test runner, added at
> 4.5). `PLANNED` = specified here, gated on the phase named (Phase 5's remaining scope —
> red-team/latency/cost proof, embedder bake-off, semantic caching (deliberately deferred, see
> `answer_cache.py`), adaptive router — is not built yet). Every code claim is anchored `file:line`
> so it can
> be checked against the tree.

---

## 0. Contents

1. [Current pipeline (as-built)](#1-current-pipeline-as-built)
2. [Target pipeline (stage by stage)](#2-target-pipeline-stage-by-stage)
3. [Source-isolation model (provider tags + RLS)](#3-source-isolation-model-provider-tags--rls)
4. [Data flow: ingestion → retrieval → answer](#4-data-flow-ingestion--retrieval--answer)
5. [The accuracy stack](#5-the-accuracy-stack)
6. [Eval + tracing scoreboard](#6-eval--tracing-scoreboard)
7. [Config & flags](#7-config--flags)
8. [Research-layer decision table](#8-research-layer-decision-table)
9. [Phasing & gates](#9-phasing--gates)

---

## 1. Current pipeline (as-built)

Two flows share one Postgres + pgvector corpus: a **write path** (ingestion, fully built and verified)
and a **read path** (retrieval, built as a library, not yet wired to HTTP).

**Write path** — `app/features/confluence_sync` → `app/features/ingestion`. A Confluence webhook
(`confluence_sync/server/webhook.py`) validates (rate limit, body cap, HMAC, fail-closed on an unset
secret), records to `event_ledger`, and enqueues a crash-safe job. A worker
(`confluence_sync/application/worker.py`) runs each job in three transactions (claim → handle+complete
→ fail) so bookkeeping and work never share a rollback. The sync handler
(`confluence_sync/application/sync_service.py`) classifies the change and, on a content change, calls
`stage_and_activate` (`ingestion/application/versioning.py`). Ingestion produces **parent + child
chunks** (`ingestion/domain/chunking.py`): parents (`kind=0`, ~1200 tok, not embedded) give context,
children (`kind=1`, ~400 tok, embedded + `tsv`) are the match unit. Each child's
`retrieval_content` is a metadata prefix + an optional LLM-written situating context
(`ingestion/application/contextualizer.py`, whole page prompt-cached), distinct from the verbatim
`display_content` used in citations. Versions are immutable; activation is a single-transaction
pointer swap with instant rollback and GC beyond a retain window (`versioning.py`).

**Read path** — `app/features/retrieval`. `HybridRetriever.retrieve(query, scope, k=5)`
(`retrieval/application/retriever.py:45`): embed the query, run **dense** (HNSW cosine, `halfvec(3072)`
cast for the >2000-dim model) ∥ **keyword** (`tsvector` GIN, implicit-AND rewritten to OR) each over
`candidate_k=40` (`retriever.py:38`), fuse with **RRF** `Σ 1/(60+rank)` (`retrieval/domain/fusion.py`),
tie-break by keyword rank, then **permission-filter** (`retrieval/domain/permission.py`) and return the
top-`k` page ids. As of Phase 4.3 the filter is DB-backed: `page_restriction` persists the real
principal list per page (written by `confluence_sync`'s `handle_sync_page`), queried fresh per search
by `search_repo.fetch_page_scopes` and fed into a request-scoped `PrincipalPermissionPolicy` — never
the whole corpus, never the fixture data the constructor-injected policy used to carry.

**Storage** — 7 tables in `app/platform/db/models.py`: `page_source` (`:85`, one per Confluence page),
`document`, `document_version` (immutable snapshot, ≤1 active per document), `chunk` (`:206`, parents +
children; hot-path columns `is_active`/`space_id`/`page_status` denormalized so search never joins),
`event_ledger`, `job`, `reconciliation_run`. Two **partial** indexes on `chunk` cover only active child
rows: HNSW over `embedding` and GIN over `tsv`.

**What is already modern — keep as-is** (do not rebuild): parent/child chunking, contextual retrieval,
RRF fusion, `halfvec@3072` HNSW, immutable versioning + atomic activation + rollback + GC, the 3-pass
re-embed reuse gate (`ingestion/domain/chunk_diff.py`), deterministic SQL filtering (no LLM filters),
and the custom eval harness with its injectable `RankFn` seam (`features/evaluation`).

**Confirmed gaps** (each maps to a phase): no source/tenant column (only `space_id`); **no reranker**
(the `reranker_*` settings at `settings.py:62-65` are dead — no client exists); pgvector image is the
rolling `pg16` tag; no request tracing; no query rewrite / answer generation / citations / refusal /
CRAG; `POST /chat` absent (the web route is a 501 stub); no caching; gold set is 12 synthetic cases.
(Principal ACL was fixture-only through 4.2 — closed in Phase 4.3, see above.)

---

## 2. Target pipeline (stage by stage)

```
scope → conversational rewrite → embed → (RLS-scoped) dense ∥ keyword → RRF
      → permission filter → cross-encoder rerank(≤75 → k) → parent-context expansion
      → grounded generation w/ forced citations → refusal threshold → one CRAG retry → SSE stream
```

| # | Stage | Where | Phase | Notes |
|---|---|---|---|---|
| 1 | Conversational rewrite | `rag_agent/infrastructure/llm_client.py` ✅ 4.2 | 4.2 | multi-turn history → standalone query; one cheap LLM call (`routing_model`), always on (`rewrite_enabled`); fails open to the verbatim query on an `AnthropicError` |
| 2 | Embed | `retriever.py` (unchanged) | — | same provider as ingestion |
| 3 | RLS-scoped dense ∥ keyword | `search_repo.py`, `retriever.py` | 3.5.1/3.5.3 | reader engine sets `app.allowed_sources` + HNSW GUCs per txn |
| 4 | RRF fusion | `fusion.py` (unchanged) | — | `Σ 1/(60+rank)`, tie-break by keyword rank |
| 5 | Permission filter | `permission.py` ✅ 4.3 | 4.3 | real persisted principal lists (`page_restriction`), queried fresh per search; runs **before** rerank |
| 6 | Cross-encoder rerank | `reranker_client.py`, `retriever.py` | 3.5.2 | `candidate_k` 40→75; rerank ≤75 → top-`k`; **after** the permission filter |
| — | One CRAG retry | `rag_agent/application/answer_service.py` ✅ 4.2 | 4.2 | if the rewritten query's top score is weak, one retry with the verbatim query (`crag_max_retries`), keeping whichever scored higher — runs *between* retrieval and refusal, not after (see below) |
| — | Refusal threshold | `rag_agent/domain/refusal.py` ✅ 4.1, wired ✅ 4.2 | 4.2 | top rerank score (post-CRAG) < `refusal_min_rerank_score` → refuse via `decide_refusal`, skip generation entirely |
| 7 | Parent-context expansion | `rag_agent/application/answer_service.py` ✅ 4.2 | 4.2 | `HybridRetriever.fetch_parent_texts` joins `parent_chunk_id`; the *parent* text grounds the generator, not the matched child |
| 8 | Grounded generation + forced citations | `rag_agent` ✅ 4.2 | 4.2 (citation core ✅ 4.1) | every claim cites a chunk; uncited claims stripped by `enforce_citations`; zero surviving citations degrades to refusal rather than an empty answer |
| 11 | SSE stream | `rag_agent/server/router.py` ✅ 4.4 | 4.4 | events `start`/`token`/`citations`/`done`/`error`; chunked-replay of the fully citation-enforced answer, not per-model-token streaming (see PLAN 4.4 deviation 1) |

Row order above matches the §2 diagram's presentation order (stage *concerns*), not runtime call
order. The actual 4.2 call order is: rerank (6) → CRAG retry → refusal check → parent expansion (7) →
generation (8) — refusing before ever attempting the corrective retry would defeat its purpose, so
the retry sits between retrieval and the refusal decision even though the diagram lists refusal before
CRAG.

Every request writes one `query_trace` row: retrieval fields in 3.5, answer/feedback fields in 4.

**Ordering invariant (security-critical):** rerank (6) runs **after** the permission filter (5) — never
score a document the principal cannot see. Both security layers (§3) apply before any text leaves the DB.

---

## 3. Source-isolation model (provider tags + RLS)

**The requirement.** One backend and one corpus power *many* chatbots. Each bot is scoped to a subset of
**source systems** (a "provider": Confluence now; Zendesk / Notion / uploads later), with a **hard
security boundary** between scopes and **default-deny**. Two layered controls, both always applied:

- **Source-level RLS** (Phase 3.5): Postgres Row-Level Security on `chunk`, keyed by `source_id`, enforced
  by a non-owner role. Isolates whole source systems.
- **Page-level principal ACL** (Phase 4): persisted principal lists enforced pre-search in the retriever.
  Enforces per-page read restrictions *within* a source.

These are distinct layers — **both apply on every read**. RLS is the security net; the explicit
`WHERE source_id = ANY(:sources)` added alongside it (§5) is correctness + recall.

### 3.1 Schema (Phase 3.5.3)

Three columns on **`page_source` and `chunk`** only (retrieval never reads `document_version`):

| Column | Type | Meaning |
|---|---|---|
| `source_type` | `String(32)` + CHECK constraint | coarse connector label (`confluence`, later `zendesk`…). CHECK, **not a PG enum**, to avoid `ALTER TYPE` friction as connectors grow. |
| `source_id` | `String(128)` | the **isolation key**, e.g. `confluence:default`. |
| `tags` | `ARRAY(Text)` | free-form per-source tags for bot scoping. |

Added `NOT NULL` with a `server_default` (backfills existing Confluence rows to
`source_id='confluence:default'`, `source_type='confluence'`, `tags='{}'`), then the **default is
dropped** so ingestion must set `source_id` explicitly going forward. New partial index
`ix_chunk_active_source (is_active, source_id) WHERE is_active`.

### 3.2 Roles

| Role | Grants | Used by |
|---|---|---|
| `rag_writer` | owner, `BYPASSRLS` | worker / webhook / reconcile / ingestion (write path) — RLS never blocks writes or trace inserts |
| `rag_reader` | login, **non-owner**, `GRANT SELECT` on read tables, **no `BYPASSRLS`** | `HybridRetriever` (read path) — RLS actually enforced |

The owner bypasses RLS, so **reads must run as `rag_reader`**. `engine.py` keeps the existing
writer sessionmaker and adds `get_reader_engine()`/`get_reader_sessionmaker()` bound to
`database_reader_url` (falls back to `database_url` if empty).

### 3.3 Policy + GUC (default-deny)

```sql
ALTER TABLE chunk ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunk FORCE  ROW LEVEL SECURITY;
CREATE POLICY chunk_source_read ON chunk FOR SELECT
  USING (source_id = ANY(string_to_array(current_setting('app.allowed_sources', true), ',')));
```

The retriever sets the scope per transaction with **`set_config` (parameter-bound), never `SET LOCAL`**
— `SET LOCAL` can't bind a parameter, which would be an injection vector or a silent default-deny:

```python
session.execute(
    text("SELECT set_config('app.allowed_sources', :s, true)"),
    {"s": ",".join(allowed_sources)},
)
```

**Default-deny proof.** Unset GUC → `current_setting('app.allowed_sources', true)` returns `NULL` →
`string_to_array(NULL, ',')` returns `NULL` → `source_id = ANY(NULL)` is never true → **zero rows**. A
retrieval that forgets to scope leaks nothing; it returns nothing. This is asserted by a negative
isolation test in the same PR (a wrong `source_id` → 0 rows; the reader cannot see unscoped rows).

### 3.4 Recall interaction (why pgvector 0.8 comes first)

A narrow RLS predicate prunes the HNSW candidate set, so an ANN scan can return **fewer than `LIMIT`**
rows — this reads like a reranker regression but is an index artifact. `hnsw.iterative_scan` is the
safety valve, and it exists only in **pgvector ≥ 0.8**. Therefore 3.5.1 (pin 0.8 + set
`hnsw.iterative_scan='relaxed_order'`, `hnsw.ef_search=100` per txn) **must land before** RLS.
`relaxed_order` is acceptable because we re-rank downstream.

---

## 4. Data flow: ingestion → retrieval → answer

**Ingestion (write, `rag_writer`).** webhook → `event_ledger` → `job` → worker → `sync_service` →
`stage_and_activate`. The **single activation point** in `versioning.py` stamps
`source_id="confluence:default"` (+ `source_type`, `tags`) — a constant today, a parameter when a
second source lands. This is the one seam that generalizes; the rest of the Confluence-specific
ingestion is **not** generalized yet (product decision 3).

**Retrieval (read, `rag_reader`).** For each request, one transaction: `set_config('app.allowed_sources',
…)` + the HNSW GUCs → dense ∥ keyword (each carrying `AND source_id = ANY(:sources)` in `_base_filters`)
→ RRF → permission filter → fetch rerank texts for the top `rerank_depth` **allowed** pages → cross-encoder
rerank → top-`k`. Write one `query_trace` row (via the **writer** engine, so RLS never blocks the insert).

**Answer (Phase 4, `rag_agent`).** rewrite → the retrieval above → parent-context expansion (join
`parent_chunk_id`, feed parent text) → grounded generation with forced numbered citations → refusal
below threshold → at most one CRAG retry → SSE stream. `PATCH /chat/{trace_id}/feedback` updates the
same trace row (writer engine).

---

## 5. The accuracy stack

- **Reranking (Phase 3.5.2, the user's called-out priority).** A new `platform/clients/reranker_client.py`
  mirrors the embeddings abstraction exactly (`EmbeddingProvider` Protocol machinery: timeout, bounded
  retry+backoff, circuit breaker, abuse cap). `Reranker` Protocol; `CohereReranker` (raw `httpx`,
  `rerank-v3.5`); `FakeReranker` (identity, deterministic — for tests and offline dev); `build_reranker`
  factory with offline fallback (empty key **or** provider ∈ {`""`,`fake`} **or** offline env →
  `FakeReranker`). **Cross-encoder rerankers only — no general-LLM rerankers** (ADR-0005). Because the
  retriever deals in page ids only, a `fetch_rerank_texts` refactor in `search_repo.py` (subject to the
  same `_base_filters` + source scope) precedes wiring; rerank is inserted **after** the permission
  filter, **before** the top-`k` slice.
- **Parent-context expansion (✅ Phase 4.2).** Children retrieve; parents ground.
  `HybridRetriever.fetch_parent_texts` joins `parent_chunk_id` and `AnswerService` sends the parent
  chunk text to the generator, so the model has enough surrounding context to answer.
- **Forced citations (✅ Phase 4.2, core built 4.1).** Every claim cites a retrieved chunk; **uncited
  claims are stripped** before returning. `enforce_citations` (`features/rag_agent/domain/citations.py`)
  keeps a sentence only if it cites a valid numbered marker, drops hallucinated-source markers, and
  returns the markers actually used. `AnswerService` now drives the real generator
  (`AnthropicAnswerGenerator`) that produces the cited text this pass enforces; if nothing survives
  enforcement, the answer degrades to a refusal rather than returning an empty string.
- **Refusal threshold (✅ Phase 4.2, core built 4.1).** If the top rerank score (after the CRAG retry,
  if one ran) is below `refusal_min_rerank_score`, refuse ("not in the docs") and route to a human
  rather than hallucinate, skipping generation entirely. `decide_refusal`
  (`features/rag_agent/domain/refusal.py`) refuses below threshold or when retrieval returned nothing;
  `AnswerService` now wires it to the live top rerank score from `retrieve_with_context`.
- **One CRAG retry (✅ Phase 4.2).** On a weak result, exactly one corrective retrieval
  (`crag_max_retries`, default 1): retries with the user's verbatim last turn (in case the rewrite hurt
  retrieval) and keeps whichever result scored higher. A no-op when rewrite is disabled/unchanged.
  Not an agent loop — a fixed workflow (ADR-0005).

**Proof of lift (Phase 3.5.5).** `make eval` reports Precision@5 and NDCG@10 **before vs after** rerank
on `retrieval_smoke.json`, keeping the report format comparable to the existing baseline. The mechanism
is `evaluate_rerank_lift` (pure, in `features/evaluation`); the *real* before/after run is the DB-backed
integration test `test_rerank_lift_before_vs_after` (reader role + RLS + indexed corpus), which writes
`eval-reports/rerank_lift.{json,md}` under `EVAL_WRITE_RERANK_REPORT=1`. `make eval` (DB-free baseline)
echoes that saved table. CI runs with `FakeReranker` → before == after → **zero lift**, the deterministic
invariant that proves the mechanism without a hosted key.

**Measured result (live Cohere `rerank-v3.5` + real OpenAI-3072 embeddings, 6-case fixture):**

| Metric | Before | After | Δ |
|---|---|---|---|
| precision@5 | 0.200 | 0.200 | +0.000 |
| ndcg@10 | 1.000 | 0.877 | **−0.123** |

The lift is **negative on this fixture** — and that is the honest, expected outcome, not a reranker
defect. `retrieval_smoke` has one relevant page per query and real dense retrieval already ranks it
**first** (before-ndcg@10 = 1.000, saturated), so the cross-encoder has no headroom to improve and its
reordering can only demote. Reranking pays off when first-stage retrieval is *imperfect* — a larger,
noisier, more ambiguous corpus — which this 6-case synthetic set is not. The genuine rerank lift is
therefore a **Phase-5 measurement on the real-ticket gold set** (§6: "gold set is 12 synthetic cases").
Consequently `refusal_min_rerank_score` is set to a **conservative provisional 0.10** (Cohere v3.5 scores
clearly-relevant docs well above this and noise below it) and **must be re-tuned on the Phase-5 gold set**,
not fixed from this fixture.

---

## 6. Eval + tracing scoreboard

**Eval.** The harness (`features/evaluation`) runs an injected `RankFn` over labelled cases and computes
recall@k, precision@k, MRR, NDCG@k, hit_rate@k. The reranker plugs into the same seam — no runner change.
3.5.5 adds a before/after rerank-lift table. Datasets: `retrieval_smoke.json` (relevance),
`permission.json` (isolation/no-leak), `ambiguity.json`. A real-ticket gold set is a Phase 5 deliverable.

**Tracing.** A `QueryTrace` ORM model + `query_trace` table, written via the **writer** engine (so RLS
never blocks the insert and the answer runtime / feedback endpoint can `UPDATE` the row).
Populated at retrieval (3.5.4, extended 4.2): `id`, `raw_query`, `retrieved_page_ids`,
`allowed_sources` (isolation audit), `embedding_model`, `reranker_model`, `latency_ms`, `created_at`,
and now `retrieved_chunk_ids` + `rerank_scores` too — every `retrieve()`/`retrieve_with_context()`
call fills them, not just the latter. **Deviation from the original plan:** rather than refactoring
`retrieve()`'s return type (which the eval harness's `RankFn` seam and several already-verified 3.5
tests depend on), 4.2 added `retrieve_with_context()` alongside it, sharing one private search core —
both write the same richer trace row. Filled by the answer workflow itself (✅ 4.2, via
`update_query_trace_answer`): `rewritten_query`, `answer`, `citations` (as `{"markers": [...]}`).
Still nullable, filled by the Phase 4.4 feedback endpoint (via `update_query_trace_feedback`, already
built): `feedback`. structlog stays for ops logging; Langfuse is a possible future exporter, not built
here.

---

## 7. Config & flags

New / changed settings in `app/platform/config/settings.py` (safe defaults; documented in `.env.example`):

| Setting | Default | Introduced | Purpose |
|---|---|---|---|
| `database_reader_url` | `""` (→ `database_url` if empty) | 3.5.3 | non-owner `rag_reader` DSN for retrieval |
| `reranker_provider` | `""` → treated as `fake` offline | (exists) 3.5.2 | `cohere` \| `fake` \| `local` |
| `rerank_candidate_k` | `75` | 3.5.2 | candidates fetched before rerank |
| `rerank_depth` | `75` | 3.5.2 | max docs sent to the cross-encoder |
| `rerank_top_k` | `5` | 3.5.2 | survivors returned |
| `hnsw_ef_search` | `100` | 3.5.1 | per-txn recall knob |
| `hnsw_iterative_scan` | `relaxed_order` | 3.5.1 | safety valve under narrow RLS scope |
| `rewrite_enabled` | `true` | 4 | conversational query rewrite on |
| `refusal_min_rerank_score` | `0.10` provisional (set 3.5.5; re-tune Phase 5) | 4 | below → refuse + route to human |
| `crag_max_retries` | `1` | 4 | corrective retrieval cap (protects p95) |
| `chat_api_key` | `""` (fail-closed if unset) | 4.4 | shared secret, `POST /chat`/`PATCH .../feedback` auth (C1) |
| `chat_api_key_previous` | `""` | 5.1 | second secret accepted in parallel during a rotation's overlap window — see `docs/runbooks/chat-api-key-rotation.md` |
| `chat_answer_cache_ttl_seconds` | `300.0` | 5.2 | exact-match `CachingAnswerService` TTL, same bounded-staleness shape as `chat_idempotency_ttl_seconds` |
| `chat_answer_cache_max_entries` | `500` | 5.2 | insertion-order eviction bound on the in-process answer cache |

**Test fixture rule (critical).** The hermetic settings fixture MUST force `reranker_provider=fake`.
`.env` carries a live Cohere key and `env=local`; the offline fallback only fires on an *empty* key, so
without this override CI would hit Cohere non-deterministically.

---

## 8. Research-layer decision table

The market-research brief (naive RAG ~44% → advanced RAG ~63% factual accuracy) proposed a stack of
upgrade layers. Each was audited against the actual code. Verdict + one-line rationale:

| Layer | Verdict | Rationale |
|---|---|---|
| Parent/child chunking | **KEEP** | already built (`chunking.py`); parent expansion is a join away |
| Contextual retrieval / contextual embeddings | **KEEP** | already built + prompt-cached (`contextualizer.py`) |
| Hybrid search (dense + sparse) | **KEEP** | dense HNSW + keyword GIN already in `search_repo.py` |
| Fusion: weighted-sum → RRF | **KEEP** | the brief's swap is already done (`fusion.py`) |
| Deterministic SQL filtering (no LLM filters) | **KEEP** | keeps recall honest; do not replace with LLM filters |
| Eval harness (Precision@k / NDCG) | **KEEP** | injectable `RankFn` seam already present |
| **Cross-encoder reranking** | **ADD (3.5.2)** | the user's priority; absent today; essential for Confluence docs |
| Provider tagging + RLS isolation | **ADD (3.5.3)** | required for many-bots-one-corpus with a hard boundary |
| pgvector 0.8 + iterative scan | **ADD (3.5.1)** | prevents RLS from silently under-returning; must be first |
| Request tracing / observability | **ADD (3.5.4)** | one `query_trace` row per request; isolation audit + Phase-4 feedback |
| Conversational query rewrite | **ADD (4)** | multi-turn → standalone query; cheap, always on |
| Grounded generation + forced citations | **ADD (4)** | strip uncited claims; the anti-hallucination core |
| Refusal / abstention threshold | **ADD (4)** | refuse below score, route to human |
| CRAG (one corrective retry) | **ADD (4)** | bounded to 1 retry to protect p95 |
| Real principal ACL storage | **DONE (4.3)** | `page_restriction` table replaces the fixture-fed policy's data source |
| Embedder bake-off / Matryoshka | **UPGRADE (5)** | multi-provider code exists; re-embed via the version-stamp gate |
| Caching (exact + semantic) | **DONE (5.2, exact-match only)** | in-process `TTLCache`, no confirmed multi-instance need for Redis yet; semantic caching deferred — accuracy risk, no traffic to tune a threshold |
| Adaptive routing (query difficulty) | **ADD (5, last)** | simple vs decompose; cheap wins first |
| HyDE / multi-query (RAG-fusion) | **DEFER (5)** | hard queries only; cost/latency not justified broadly |
| Self-RAG / agent loop | **REJECT** | a fixed workflow is more testable and bounds latency (ADR-0005) |
| General-LLM reranker | **REJECT** | cross-encoder only — cheaper, deterministic, purpose-built (ADR-0005) |
| Graph RAG | **REJECT** | cost/latency unjustified for this corpus |

---

## 9. Phasing & gates

- **Phase 0 (this doc + ADR-0004/0005).** No code. **Gate: user reviews `DESIGN.md` before any Phase 3.5
  code begins.** The two ADR decisions must be settled first.
- **Phase 3.5** — accuracy + tagging spine, offline-measurable, no chat. Sub-steps run in order:
  3.5.1 pin pgvector 0.8 → 3.5.2 reranker → 3.5.3 provider tags + RLS + reader role (shipped atomically
  with the eval-harness update) → 3.5.4 tracing → 3.5.5 measure. **Exit gate:** `make check` green,
  `make eval` shows rerank lift, isolation tests pass, pgvector ≥ 0.8, every retrieval traced.
- **Phase 4** — answer runtime + streaming chat (`rag_agent`, `POST /chat`, web UI). Fixed workflow.
  4.1 (DTO contract + refusal/citation domain core), 4.2 (the full `AnswerService` pipeline,
  network-free-tested), 4.3 (real, persisted principal ACL), 4.4 (`POST /chat` +
  `PATCH /chat/{trace_id}/feedback`, full `securing-http-and-llm-endpoints` control set), and 4.5
  (web chat UI + contract extension, live-verified end to end) are **all done**.
- **Phase 5** — optimization + proof. **5.1 (`CHAT_API_KEY` rotation mechanism) and 5.2 (exact-match
  answer caching) are done** — dual-key overlap window + rotation script + runbook (5.1);
  `CachingAnswerService` wrapping `AnswerService`, semantic caching deliberately deferred (5.2).
  Remaining, reordered around the 5.2-scoping blocker (2026-08-10): red-team/latency/cost proof
  next, then the embedder bake-off (blocked on a real gold set — the Confluence token is still
  dead — and `VOYAGE_API_KEY`), then adaptive routing last.

**Cross-cutting rules (every phase).** Feature boundaries: export new cross-boundary symbols from the
feature/capability root, never deep-import; run `make boundaries` before every commit. No-regression on
ruff/pyright at the ADR-0003 D1 baseline (2/25 ruff, 31/1 pyright) — bring touched files clean, do not
reformat untouched files. `make check` stays green. Migrations are reversible and ordered from
`0001_core_schema`.

## 10. Confluence source scoping — implemented (PLAN 3.5.6)

A brainstorm (per `superpowers:brainstorming`) on letting Confluence sync be scoped to individual
pages / page-subtrees, not just whole spaces, concluded 2026-08-10 with an approved design, planned
and shipped the same day. **Implemented:** a DB-backed `source_scope` table + a zero-network
resolver (`confluence_sync/domain/scope_resolver.py`; tree-walks the `parent_id` already returned by
`list_space_pages` — no new Confluence API call) feeding an optional narrowing into the existing
`reconciliation.py` diff/deactivate engine, with purge-on-removal and `tags`-based bot scoping.
`CONFLUENCE_SPACES`/`confluence_scope_list` — dead code, zero consumers — are deleted; rows are
seeded one-off via `scripts/seed_source_scope.py`.

Two things worth knowing that weren't obvious from the original design note:

- **Reconciliation's space discovery now unions in scope-implied spaces**, not just spaces already
  present in `page_source`. This is what lets a brand-new space (or a space that only ever existed
  as a `source_scope` row) get its first sweep at all — `CONFLUENCE_SPACES` never had this
  capability even when non-empty, since nothing consumed it.
- **`resolve_space_scope` distinguishes "no rows ever" from "rows exist, all inactive."** The
  former is unrestricted (today's default); the latter restricts to the empty set, so deactivating
  a space's last root purges everything it covered rather than silently reverting to unrestricted.

Full schema, resolver contract, reconciliation integration, and test plan are in
`docs/superpowers/specs/2026-08-10-confluence-source-scoping-design.md`; status/decision history is
in `docs/rag/PLAN.md` §0.
