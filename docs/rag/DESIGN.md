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
> `TODAY` = shipped and verified (Phases 1–3, 99 tests green). `PLANNED` = specified here, gated on
> the phase named. Every code claim is anchored `file:line` so it can be checked against the tree.

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
top-`k` page ids. The filter is fixture-fed today — the DB stores an access-scope *hash*, not principal
lists.

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
CRAG; principal ACL is fixture-only; `POST /chat` absent (the web route is a 501 stub); no caching;
gold set is 12 synthetic cases.

---

## 2. Target pipeline (stage by stage)

```
scope → conversational rewrite → embed → (RLS-scoped) dense ∥ keyword → RRF
      → permission filter → cross-encoder rerank(≤75 → k) → parent-context expansion
      → grounded generation w/ forced citations → refusal threshold → one CRAG retry → SSE stream
```

| # | Stage | Where | Phase | Notes |
|---|---|---|---|---|
| 1 | Conversational rewrite | `rag_agent` (new) | 4 | multi-turn history → standalone query; one cheap LLM call (`routing_model`), always on |
| 2 | Embed | `retriever.py` (unchanged) | — | same provider as ingestion |
| 3 | RLS-scoped dense ∥ keyword | `search_repo.py`, `retriever.py` | 3.5.1/3.5.3 | reader engine sets `app.allowed_sources` + HNSW GUCs per txn |
| 4 | RRF fusion | `fusion.py` (unchanged) | — | `Σ 1/(60+rank)`, tie-break by keyword rank |
| 5 | Permission filter | `permission.py` | 4 | fixture ACL → real persisted principal lists; runs **before** rerank |
| 6 | Cross-encoder rerank | `reranker_client.py` (new), `retriever.py` | 3.5.2 | `candidate_k` 40→75; rerank ≤75 → top-`k`; **after** the permission filter |
| 7 | Parent-context expansion | `rag_agent` | 4 | join `parent_chunk_id`; feed the *parent* text to the generator |
| 8 | Grounded generation + forced citations | `rag_agent` | 4 | every claim cites a chunk; uncited claims are stripped |
| 9 | Refusal threshold | `rag_agent` | 4 | top rerank score < `refusal_min_rerank_score` → refuse + route to human |
| 10 | One CRAG retry | `rag_agent` | 4 | at most one corrective retrieval (`crag_max_retries=1`) to protect p95 |
| 11 | SSE stream | `POST /chat` in `main.py` | 4 | events `start`/`token`/`citations`/`done`, reader engine |

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
- **Parent-context expansion (Phase 4).** Children retrieve; parents ground. Join `parent_chunk_id` and
  send the parent chunk text to the generator, so the model has enough surrounding context to answer.
- **Forced citations (Phase 4).** Every claim cites a retrieved chunk; **uncited claims are stripped**
  before returning.
- **Refusal threshold (Phase 4).** If the top rerank score < `refusal_min_rerank_score`, refuse ("not in
  the docs") and route to a human rather than hallucinate. The threshold is tuned from the 3.5.5 numbers.
- **One CRAG retry (Phase 4).** On a weak result, exactly one corrective retrieval (`crag_max_retries=1`),
  to protect p95. Not an agent loop — a fixed workflow (ADR-0005).

**Proof of lift (Phase 3.5.5).** `make eval` reports Precision@5 and NDCG@10 **before vs after** rerank
on `retrieval_smoke.json`, keeping the report format comparable to the existing baseline. The after-rerank
numbers become the new baseline and set `refusal_min_rerank_score`.

---

## 6. Eval + tracing scoreboard

**Eval.** The harness (`features/evaluation`) runs an injected `RankFn` over labelled cases and computes
recall@k, precision@k, MRR, NDCG@k, hit_rate@k. The reranker plugs into the same seam — no runner change.
3.5.5 adds a before/after rerank-lift table. Datasets: `retrieval_smoke.json` (relevance),
`permission.json` (isolation/no-leak), `ambiguity.json`. A real-ticket gold set is a Phase 5 deliverable.

**Tracing.** A new `QueryTrace` ORM model + `query_trace` table, written via the **writer** engine (so
RLS never blocks the insert and Phase-4 feedback can `UPDATE` the row). Populated **now** (retrieval):
`id`, `raw_query`, `retrieved_page_ids`, `retrieved_chunk_ids`, `rerank_scores`, `allowed_sources`
(isolation audit), `embedding_model`, `reranker_model`, `latency_ms`, `created_at`. **Nullable, filled in
Phase 4**: `rewritten_query`, `answer`, `citations`, `feedback`. structlog stays for ops logging; Langfuse
is a possible future exporter, not built here.

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
| `refusal_min_rerank_score` | tuned in 3.5.5 | 4 | below → refuse + route to human |
| `crag_max_retries` | `1` | 4 | corrective retrieval cap (protects p95) |

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
| Real principal ACL storage | **UPGRADE (4)** | replace fixture-fed policy with persisted principal lists |
| Embedder bake-off / Matryoshka | **UPGRADE (5)** | multi-provider code exists; re-embed via the version-stamp gate |
| Caching (exact + semantic) | **ADD (5, gated)** | Redis only if the proportionality gate is met |
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
- **Phase 5** — optimization + proof (embedder bake-off, caching, adaptive routing, red-team, latency/cost).

**Cross-cutting rules (every phase).** Feature boundaries: export new cross-boundary symbols from the
feature/capability root, never deep-import; run `make boundaries` before every commit. No-regression on
ruff/pyright at the ADR-0003 D1 baseline (2/25 ruff, 31/1 pyright) — bring touched files clean, do not
reformat untouched files. `make check` stays green. Migrations are reversible and ordered from
`0001_core_schema`.
