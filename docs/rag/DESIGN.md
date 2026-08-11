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
> **and Phase 5.3**, a deterministic prompt-injection + permission/isolation red-team pass that
> found and fixed a real bypass (an unvalidated `principal` could claim numeric space-level trust
> and skip page-level restrictions; closed with a `ChatRequestBody` validator) —
> **and Phase 4.6.1 through 4.6.12** (fixes-backlog remediation, gating Phase 5.4 — see
> `PLAN.md`'s "4.6 progress snapshot" for the full table): a CRITICAL Confluence
> group-restriction bypass closed fail-closed then resolved via real group-membership expansion; a
> HIGH cross-principal idempotency-cache leak closed; the rate limiter/idempotency cache hardened
> (IP-only keying, bounded memory); `rollback_to` now restores `PageSource`'s cached hashes so a
> post-rollback resync can't be silently masked as "no change"; the domain-layer `scope` string can
> no longer be reinterpreted as space-vs-principal trust by shape alone
> (`permission.classify_scope`); the Confluence REST client gained a circuit breaker, real 5xx
> retry, and audit logging; a duplicate `source_type`/`root_type` CHECK constraint (live on the dev
> DB's `chunk`/`page_source` tables since the Phase-1 baseline) was found and removed (migration
> `0006_dedupe_source_type_check`); the pyright baseline was formally reconciled 31→34
> (ADR-0003 D1); the RLS reader role now fails closed instead of silently running as the
> RLS-bypassing writer outside local/test/dev/ci; a same-`delivery_id`/different-hash webhook
> redelivery now dedupes gracefully instead of a 500; and `refusal_reason` now reaches the
> `chat_request` structured log line (4.6.12) —
> **274 backend tests green** (plus 39 `apps/web` vitest tests, its first test runner, added at
> 4.5). `PLANNED` = specified here, gated on the phase named: **4.6.13 through 4.6.16** (the
> fixes-backlog exit gate) are still open — see `PLAN.md` for exact remaining scope — and Phase 5's
> remaining scope (a live-LLM adversarial pass + latency/cost proof (5.4), embedder bake-off,
> semantic caching (deliberately deferred, see `answer_cache.py`), adaptive router) is not built yet
> and is blocked on 4.6.16 going green. Every code claim is anchored `file:line` so it can be
> checked against the tree, though the file:line anchors below predate the 4.6.x fixes and have not
> all been re-verified against the current line numbers (content is still accurate; do not trust
> exact line numbers without a `grep` first).

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
10. [Confluence source scoping — implemented](#10-confluence-source-scoping--implemented-plan-356)
11. [Ambiguity clarification and fallback — designed, not started](#11-ambiguity-clarification-and-fallback--designed-not-started-plan-phase-9)
12. [Vision-grounded image analysis — designed, not started](#12-vision-grounded-image-analysis--designed-not-started-plan-phase-7)

---

## 1. Current pipeline (as-built)

Two flows share one Postgres + pgvector corpus: a **write path** (ingestion, fully built and verified)
and a **read path** (retrieval, wired to a live, secured `POST /chat` SSE endpoint since Phase 4.4 —
see §2 for the full answer-workflow pipeline built on top of it).

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

**Storage** — 10 tables in `app/platform/db/models.py`: `page_source` (`:85`, one per Confluence page),
`page_restriction` (Phase 4.3, persisted per-page principal ACL), `document`, `document_version`
(immutable snapshot, ≤1 active per document), `chunk` (`:206`, parents + children; hot-path columns
`is_active`/`space_id`/`page_status` denormalized so search never joins), `event_ledger`, `job`,
`reconciliation_run`, `source_scope` (PLAN 3.5.6), `query_trace` (PLAN 3.5.4, extended in Phase 4
with the answer/citation/feedback columns). Two **partial** indexes on `chunk` cover only active
child rows: HNSW over `embedding` and GIN over `tsv`.

**What is already modern — keep as-is** (do not rebuild): parent/child chunking, contextual retrieval,
RRF fusion, `halfvec@3072` HNSW, immutable versioning + atomic activation + rollback + GC, the 3-pass
re-embed reuse gate (`ingestion/domain/chunk_diff.py`), deterministic SQL filtering (no LLM filters),
and the custom eval harness with its injectable `RankFn` seam (`features/evaluation`).

**Historical gaps, now closed (kept here so the "as-built" story reads start to finish, not because
they're still open — see the banner above and `PLAN.md` for exact current status):** the
source/tenant column, reranker, request tracing, query rewrite/answer generation/citations/
refusal/CRAG, `POST /chat`, and caching were all absent when this section was first written; every
one of them shipped between Phase 3.5.2 and Phase 5.2 and is described in full in §2 and §5 below.
Principal ACL was fixture-only through 4.2 — closed in Phase 4.3 (real `page_restriction` storage),
then hardened twice more in the Phase 4.6 fixes-backlog: 4.6.1/4.6.2 closed a group-restriction
bypass, 4.6.6 removed the domain layer's ability to reinterpret a numeric principal as space-level
trust. **Gaps still genuinely open today:** the pgvector image is still the rolling `pg16` tag (no
pinned version); the gold set is still the 12-case synthetic fixture corpus (no real gold set — see
blocker #3, Confluence token still dead); Phase 5.4 (live-LLM adversarial red-team + real
latency/cost measurement), the embedder bake-off, semantic caching, and adaptive routing are all
still unbuilt and blocked on the Phase 4.6 exit gate (4.6.16) going green.

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
- **Phase 5** — optimization + proof. **5.1 (`CHAT_API_KEY` rotation mechanism), 5.2 (exact-match
  answer caching), and 5.3 (prompt-injection + permission/isolation red-team) are done** — dual-key
  overlap window + rotation script + runbook (5.1); `CachingAnswerService` wrapping `AnswerService`,
  semantic caching deliberately deferred (5.2); deterministic architecture-level red-team tests that
  found and fixed a real numeric-`principal` space-trust bypass (5.3, see PLAN.md §0). Remaining:
  5.4 — a live-LLM adversarial pass (retrieved-content injection, system-prompt exfiltration,
  multi-turn injection, reranker relevance-poisoning) + measured latency/cost proof, both requiring
  real API spend — then the embedder bake-off (blocked on a real gold set — the Confluence token is
  still dead — and `VOYAGE_API_KEY`), then adaptive routing last.

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

## 11. Ambiguity clarification and fallback — designed, not started (PLAN Phase 9)

Scoped 2026-08-11 from an external best-practices brief on unanswerable/vague-query fallback and
`docs/future-ideas/IDEAS.md` #1. Full decision record is `docs/adr/0008-Ambiguity-Clarification-
Fallback.md`; this section is the design summary. **Deliberately sequenced after Phase 7 and Phase
4.8** (by explicit user direction, not a technical dependency — see PLAN.md §0) — this section and
ADR-0008 are documentation only, written now; no code lands under them until both of those phases
are done.

**Problem.** The fixed pipeline from §5/ADR-0005 (rewrite → retrieve → rerank → refuse) has no
concept of "this question is too vague to search well" — an under-specified query (e.g. "What are
the limits?" against a corpus covering both expense limits and approval thresholds) runs the full
grounded pipeline and lands on either a low-confidence guess or the same refusal string used for
"not in the corpus at all." All three internal refusal causes (no candidates, weak rerank score, no
citation survived enforcement) also render identical copy, so the user can't tell them apart.

**Design.**

- **A new pre-retrieval short-circuit**, `rag_agent/domain/clarification.py::decide_clarification`,
  structurally identical to the existing small-talk fix (§ current pipeline, `is_small_talk`):
  heuristic first, LLM fallback only when inconclusive, wired into `AnswerService.answer` ahead of
  rewrite/retrieval/CRAG/refusal. Feature-flagged (`enable_clarification_branch`, default off).
- **Contract change is additive, not a new SSE event.** `Answer` gains `needs_clarification: bool`,
  `clarification_question: str | None`, `clarification_options: list[str] | None`. A clarification
  reply streams over the existing `token` events (same as small-talk) with `citations: []`; the
  `done` payload carries the new fields. The `start`/`token`/`citations`/`done` lifecycle (ADR-0005
  §10) is unchanged.
- **A three-value refusal-reason taxonomy** — `no_candidates | weak_score | no_citations` — surfaced
  (not just logged) so distinct, honest copy can be shown per cause. Clarification is deliberately
  outside this taxonomy: `needs_clarification=True` is an open conversation turn, not a refusal.
- **Human hand-off stays a stub this phase**, by explicit user decision: a structured log record
  (`trace_id`, `raw_query`, `refusal_reason`) on every `refused=True` answer, plus a static "connect
  me to a human" CTA in the widget. No webhook/ticket/email integration. Salesforce is the noted
  eventual target — see `docs/future-ideas/IDEAS.md` #1 — deferred until actually prioritized.
- **Evaluation reuses the existing `ambiguity` `EvalKind`** (already in the closed 5-way Literal,
  `evaluation/schemas.py`); its 3 existing cases (`evaluation/datasets/ambiguity.json`) are extended
  to assert `needs_clarification=True`, not just `expected_answer` text. A genuinely out-of-corpus
  case is a `retrieval`/`answer`-kind case with an empty relevant-chunk set — no new `EvalKind`.
  A `fallback_rate` metric and a lightweight faithfulness/hallucination-rate signal are added to
  `evaluation/metrics/`.

**Explicit non-goals** (present in the source brief, rejected for this problem): MMR/diversity
filtering (doesn't address unanswerable/vague queries; would touch the already-shipped ADR-0005
retrieval pipeline for no benefit here); a new vector store or search engine (Postgres+pgvector+
Cohere stays the stack, ADR-0001/0002); an agent-loop rewrite of `AnswerService` (stays a fixed
pipeline per ADR-0005 decision 5 — this is one more short-circuit, not a planner).

**Open implementation question flagged for 9.2/9.3, not yet decided:** the relative ordering of the
two pre-pipeline branches (small-talk vs. clarification) when a query is arguably both, e.g. "hi,
what's the approval process?" — needs an explicit tie-break at implementation time.

Sub-step roadmap (9.1 design doc/ADR — this section — through 9.9 exit gate) is in `docs/rag/
PLAN.md`'s own Phase 9 section, not duplicated here.

## 12. Vision-grounded image analysis — designed, not started (PLAN Phase 7)

Scoped 2026-08-11 from `docs/future-ideas/IDEAS.md` #3 ("screenshot-grounded guidance") and Phase
4.7.8's click-to-zoom preview, which exposed that the analysis half was never built. Full decision
record is `docs/adr/0009-Vision-Grounded-Image-Analysis.md`; this section is the design summary.
Sequenced first in the explicit user-set order **Phase 7 → Phase 4.8 → Phase 9** — this section and
ADR-0009 are documentation only; no code lands under them until picked up as its own phase.

**Problem.** Phase 4.7 added image attachments and real screenshot capture, but both are dropped
before `onSend` with a "not analyzed yet" notice — no image ever reaches `apps/automation`. A
question like "what's on this screenshot?" or "what should I click next here?" cannot be answered.

**Design.**

- **Inline base64 on the newest `ChatTurn` only**, not a separate upload endpoint and not
  replayed on every history resend — matches the existing stateless, whole-history-resent request
  shape (PLAN 4.4 decision 2) with zero new persistent storage, and avoids multiplying image-token
  cost by conversation length.
- **Retrieval still runs; only `decide_refusal` changes.** Unlike small-talk/clarification (which
  skip retrieval), an image-bearing turn still attempts the full rewrite → retrieve → rerank → CRAG
  path, since a query can need both Confluence evidence and image content at once.
  `decide_refusal` gains a `has_image: bool` input so a turn whose text retrieval found nothing
  doesn't incorrectly refuse when the image alone can answer it.
- **A second, independent generation call — not merged into the citation-enforced grounded
  call.** A new `AnswerGenerator.generate_image_analysis`, structurally parallel to
  `generate_small_talk` (same fail-open shape on `AnthropicError`), carries the image content
  blocks and the question, produces no citation markers, and is never passed through
  `enforce_citations`. Its text is appended to the grounded answer as a clearly labeled section.
  This keeps every ADR-0005-governed citation/refusal guarantee for the *grounded* portion of the
  answer completely unchanged — an image can never forge a fake Confluence citation.
- **Contract change is additive.** `ChatTurn` gains optional `images: ImageAttachment[]`; `Answer`/
  `ChatDoneEvent` gain optional `imageAnalysis: string | null`. No new SSE event — the analysis text
  streams over the existing `token` events, same shape ADR-0008 used for clarification.
- **C6 PII redaction does not extend to image bytes.** `redact_pii` stays text-only; this is a
  documented, accepted gap this phase, disclosed to the user via composer copy, not a silently
  ignored one.
- **New C3/C10 controls, values not yet decided.** A per-turn image-count cap and a per-image
  byte-size cap are required before shipping, enforced at the same validation point as
  `chat_max_history_turns`/`chat_max_message_chars` — but per the Architecture Standard's rule
  against inventing cost/scaling numbers, the concrete values need either a real vision-token cost
  measurement or an explicit product ceiling, neither of which exists yet.
- **Image-borne prompt injection is a new threat class**, flagged for a required live-model
  adversarial pass (`securing-http-and-llm-endpoints`) before shipping — not solved by the design
  alone, since a screenshot could contain text crafted to look like a system instruction.

**Explicit non-goals for this ADR:** does not build real image PII redaction (CV/NER) — flagged as
a future-phase gap. Does not merge image content into the same call citation enforcement scores —
rejected, see ADR-0009's alternatives.

Sub-step roadmap (7.1 design doc/ADR — this section — onward) is in `docs/rag/PLAN.md`'s own Phase
7 section, not duplicated here.
