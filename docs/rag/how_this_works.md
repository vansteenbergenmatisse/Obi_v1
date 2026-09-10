# How This Works — Omniboost RAG, A-to-Z

> The short explainer: the 60-second picture, the data model, and one worked example, for how the
> Confluence RAG system ingests, stores, retrieves, answers, and streams a chat response. Phases
> 0–5.3, 4.6, 4.7, 7, and 9 are shipped; Phase 5.4 (live-LLM red-team, embedder bake-off, adaptive
> routing) and Phase 6 (Supabase migration) are still `PLANNED` — see `PLAN.md` §0 for the live
> ledger.
>
> **The detailed, phase-by-phase narrative moved out of this file** into two folders, one per side
> of the system: [`docs/rag/ingestion/`](./ingestion/README.md) (the write path — Confluence sync +
> chunking/contextualization/versioning) and [`docs/rag/retrieval/`](./retrieval/README.md) (the
> read/answer path — hybrid search, the `rag_agent` runtime, chat). Each phase there states exactly
> what happened and which files/folders it uses; that's the version to read when you need
> file:line-level detail. This file stays the short index — read it first, then follow a link.
>
> Every claim is anchored to a file so you can check it against the code. Keep this banner, the
> data model, and the worked example below current; keep the phase-by-phase detail current in the
> two folders instead — see the root `CLAUDE.md` for that rule.

---

## 0. Table of contents

1. [The 60-second picture](#1-the-60-second-picture)
2. [Where the code lives](#2-where-the-code-lives)
3. [The data model (the 11 tables)](#3-the-data-model-the-11-tables)
4. [Getting data IN — Confluence sync](#4-getting-data-in--confluence-sync)
5. [Turning a page into chunks — ingestion](#5-turning-a-page-into-chunks--ingestion)
6. [Versioning, activation, rollback](#6-versioning-activation-rollback)
7. [Getting answers OUT — retrieval, the answer runtime, and chat](#7-getting-answers-out--retrieval-the-answer-runtime-and-chat)
8. [Measuring quality — evaluation](#8-measuring-quality--evaluation)
9. [A full worked example (end to end)](#9-a-full-worked-example-end-to-end)
10. [What the PLAN adds (3.5 → 9)](#10-what-the-plan-adds-35--9)
11. [How to evaluate "are we doing the right thing?"](#11-how-to-evaluate-are-we-doing-the-right-thing)
12. [Confluence source scoping — implemented](#12-confluence-source-scoping--implemented-plan-356)

---

## 1. The 60-second picture

Two independent flows share one Postgres corpus.

```mermaid
flowchart LR
  subgraph IN["INGESTION  (write path — TODAY)"]
    CF[Confluence] -->|webhook / poll| WH[webhook + job queue]
    WH --> WK[worker]
    WK --> SYNC[sync_service: fetch + classify change]
    SYNC --> CHUNK[chunk → contextualize → embed]
    CHUNK --> VER[stage new version → atomic activate]
  end
  subgraph DB[(Postgres + pgvector, RLS-isolated by source_id)]
    T1[page_source + page_restriction]
    T2[document_version]
    T3[chunk: parents + children<br/>embedding + tsv]
  end
  VER --> DB
  subgraph OUT["RETRIEVAL + ANSWER  (read path — TODAY)"]
    Q[user question] --> RW[query rewrite]
    RW --> R[HybridRetriever]
    R -->|dense ∥ keyword → RRF → permission → rerank| DB
    DB --> CRAG[weak result? one CRAG retry]
    CRAG --> REF[refusal threshold]
    REF --> PX[parent-context expansion]
    PX --> GEN[grounded generation + forced citations]
    GEN --> SSE[POST /chat, SSE stream]
  end
```

- **Write path (ingestion)** is fully built and verified. Confluence changes flow through a webhook,
  a crash-safe job queue, and an idempotent, version-aware indexer that produces **parent + child
  chunks** with **dense embeddings** and **keyword vectors**, isolated per source by Postgres RLS.
- **Read + answer path** is fully built and wired to HTTP: `HybridRetriever` (dense ∥ keyword → RRF
  → permission filter → cross-encoder rerank) feeds the `rag_agent` answer runtime (query rewrite →
  one corrective retry on a weak result → refusal decision → parent-context expansion → grounded
  generation with forced citations), streamed to the browser over `POST /chat`'s SSE response.
- Still **PLANNED**: Phase 5's remaining scope — a live-LLM adversarial red-team pass with a
  latency/cost proof (5.4), an embedder bake-off, and adaptive routing — plus Phase 6 (the Supabase
  vector store migration & deploy). See [§10](#10-what-the-plan-adds-35--9) and `PLAN.md`.

**Core design choices** (why it looks the way it does):

| Choice | Why |
|---|---|
| **Parent/child chunking** | children are small + precise for matching; parents give the model enough surrounding context to answer |
| **Hybrid search (dense + keyword)** | semantic recall *and* exact-term precision; fused with RRF so neither dominates |
| **Immutable versions + atomic activation** | an index update is all-or-nothing; the live corpus is never half-rebuilt, and rollback is instant |
| **Contextual retrieval** | each child is embedded with a short situating context, which materially lifts recall on terse Confluence snippets |
| **Deterministic offline mode** | a `Fake` embedder + fixture Confluence corpus means the whole system runs and tests without any API key |

---

## 2. Where the code lives

```
apps/automation/app/
├── main.py                     # FastAPI wiring: gateway choice, webhook + chat routers, scheduler
├── features/
│   ├── confluence_sync/        # IN: webhook, job queue/worker, reconciliation
│   ├── ingestion/              # transform: chunking, contextualization, versioning, change-detect
│   ├── retrieval/              # OUT: hybrid search + rerank + permission filtering
│   ├── rag_agent/              # answer runtime + POST /chat SSE + feedback (PLAN 4)
│   └── evaluation/             # quality: metrics + datasets + baseline runner
├── platform/
│   ├── clients/                # Confluence, embeddings, Anthropic, reranker (Cohere/Fake)
│   ├── db/                     # models.py (the 11 tables), engine.py (sessions)
│   ├── jobs/                   # the generic job queue (claim/complete/fail/reap)
│   └── config/settings.py      # all env-driven config
└── shared/                     # hashing.py, rate_limiter.py, ttl_cache.py — cross-feature primitives
```

Each feature exposes **one public `__init__.py`**; other code imports only through that root
(machine-enforced by `tools/check_feature_boundaries.py`, run via `make boundaries`). This matters
when you read the code: `from app.features.ingestion import stage_and_activate` is the contract;
reaching into `app.features.ingestion.application.versioning` from outside would fail the build.

---

## 3. The data model (the 11 tables)

Defined in `app/platform/db/models.py`. The relationships:

```mermaid
erDiagram
  PAGE_SOURCE ||--|| DOCUMENT : "1 per page"
  PAGE_SOURCE ||--o{ PAGE_RESTRICTION : "0..n allowed principals"
  DOCUMENT ||--o{ DOCUMENT_VERSION : "many versions"
  DOCUMENT_VERSION ||--o{ CHUNK : "parents + children"
  CHUNK ||--o{ CHUNK : "parent_chunk_id (child→parent)"
  EVENT_LEDGER ||--o{ JOB : "source_event_id"
  PAGE_SOURCE {
    bigint page_id PK "Confluence page id"
    bigint space_id
    int current_cf_version
    bigint active_doc_version_id "→ the live version"
    enum page_status "current/trashed/deleted…"
    bytea content_hash "change detection"
    bytea access_scope_hash "ACL fingerprint"
  }
  PAGE_RESTRICTION {
    bigint page_id PK_FK "→ page_source"
    string principal PK "allowed reader; any row = page is restricted"
  }
  DOCUMENT_VERSION {
    bigint id PK
    enum state "staging/active/superseded/failed"
    int cf_version
    string embedding_model
    int embedding_dim
  }
  CHUNK {
    bigint id PK
    smallint kind "0=parent 1=child"
    bigint parent_chunk_id "child→parent"
    text display_content "verbatim, for citations"
    text retrieval_content "contextual, what gets embedded"
    vector embedding "children only"
    tsvector tsv "children only, keyword index"
    bool is_active "hot-path filter"
    bigint space_id
  }
```

Table by table:

| Table | One row per | Purpose |
|---|---|---|
| **`page_source`** | Confluence page | canonical registry: title, space, `active_doc_version_id` pointer, change-detection hashes, pipeline version stamps |
| **`page_restriction`** | (page, allowed principal) | persisted per-page read ACL (PLAN 4.3) — a page with zero rows is unrestricted; queried fresh per search alongside RLS as the page-level security layer, replacing the old fixture-fed policy |
| **`document`** | page | stable logical identity (survives across versions) |
| **`document_version`** | (page × cf_version × pipeline-config) | immutable snapshot; `state` ∈ staging/active/superseded/failed; **at most one `active` per document** (partial unique index) |
| **`chunk`** | parent section OR child window | the searchable rows. `kind=0` parent (not embedded), `kind=1` child (embedded + `tsv`). Hot-path filter columns (`is_active`, `space_id`, `page_status`) are denormalized here so search never joins |
| **`event_ledger`** | webhook/reconcile delivery | dedup + audit. Unique on `payload_hash`; partial-unique on `delivery_id` |
| **`job`** | unit of background work | crash-safe queue. Unique on `idempotency_key` |
| **`reconciliation_run`** | drift sweep | report: pages scanned, drift detected, jobs enqueued |
| **`source_scope`** | a configured sync root | `space` or `page` root narrowing/tagging reconciliation (PLAN 3.5.6); unique on `(root_type, root_id)` |
| **`query_trace`** | retrieval + answer request | tracing scoreboard (PLAN 3.5.4, extended by Phase 4): retrieved page/chunk ids, allowed sources, models, rerank scores, latency, plus the Phase-4 answer columns (`rewritten_query`, `answer`, `citations`, `feedback`) written by the answer runtime on the same row |
| **`curated_knowledge_entry`** | hand-authored entry | knowledge always eligible for retrieval, independent of any Confluence page (PLAN 10.2). `tags` mirrors `chunk`/`page_source` scope tagging — empty = every scope; reuses the citation machinery at retrieval time |

**Two search indexes on `chunk`** (both partial — they only cover *active child* rows, which keeps
them small and fast; `models.py:58-74, 267-272`):

- **Dense (HNSW):** over `embedding`, cosine. For models > 2000 dims (e.g. OpenAI-3072) the index is
  a `halfvec(3072)` cast — pgvector caps a full `vector` HNSW at 2000 dims, and half-precision has
  negligible recall impact. `WHERE is_active AND kind = 1 AND embedding IS NOT NULL`.
- **Keyword (GIN):** over `tsv`. `WHERE is_active AND kind = 1`.

---

## 4. Getting data IN — Confluence sync

`app/features/confluence_sync/`. Webhooks (real-time) and reconciliation (a safety-net sweep) both
feed one job queue that a worker drains into `ingestion.stage_and_activate`.

**Full phase-by-phase detail — webhook sequence, event dedup, job queue, the worker's
three-transaction discipline, sync-outcome classification, reconciliation + source scoping, and the
live/fixture gateway — now lives in [`ingestion/`](./ingestion/):**
[phase-1.md](./ingestion/phase-1.md) (Confluence sync core) and
[phase-4.6.md](./ingestion/phase-4.6.md) (group-restriction fail-closed, client hardening, event-
dedup fix, attachment extraction wiring). Start at [`ingestion/README.md`](./ingestion/README.md).

---

## 5. Turning a page into chunks — ingestion

`app/features/ingestion/`. The transform: raw Confluence storage HTML → normalized blocks →
parent/child chunks → contextual text → embeddings → rows.

**Full detail — chunking rules, display-vs-retrieval content, contextual retrieval, the keyword
`tsv`, and incremental re-embedding — now lives in
[`ingestion/phase-2.md`](./ingestion/phase-2.md).**

---

## 6. Versioning, activation, rollback

`application/versioning.py`. An index update is **immutable and atomic**: build a new version fully,
validate it, then swap a single pointer — staging → active → superseded → (rollback or GC).

**Full detail — the `stage_and_activate` transaction, the activation pointer-swap, rollback, and
deletion — now lives in [`ingestion/phase-2.md`](./ingestion/phase-2.md) (same file as chunking:
they're one pipeline). Provider tagging and source scoping (the ingestion half of PLAN 3.5) are in
[`ingestion/phase-3.5.md`](./ingestion/phase-3.5.md).**

---

## 7. Getting answers OUT — retrieval, the answer runtime, and chat

`app/features/retrieval/` is the hybrid search engine; `app/features/rag_agent/` (PLAN 4) is the
answer workflow and the `POST /chat` HTTP surface built on top of it. Both are live: `rag_agent`'s
router is mounted in `main.py` (`app.include_router(chat_router)`), and it is `retrieval`'s only
consumer.

**Full phase-by-phase detail — the retrieval pipeline (dense ∥ keyword → RRF → permission filter →
rerank), the permission model, the answer runtime (rewrite → CRAG → refuse → expand → generate →
cite), and the chat HTTP surface — now lives in [`retrieval/`](./retrieval/):**
[phase-3.md](./retrieval/phase-3.md) (original hybrid retriever),
[phase-3.5.md](./retrieval/phase-3.5.md) (pgvector/HNSW, reranker, RLS enforcement, `query_trace`),
[phase-4.md](./retrieval/phase-4.md) (answer runtime + `POST /chat`), and
[phase-4.6.md](./retrieval/phase-4.6.md) (idempotency/rate-limit/scope-classification fixes). Start
at [`retrieval/README.md`](./retrieval/README.md).

---

## 8. Measuring quality — evaluation

`app/features/evaluation/`. The harness is how we prove a change actually helped.

- **`evaluate(dataset, rank_fn, now_iso, k=5)`** (`runner.py:38-76`) runs an injected ranking
  function over every labelled case and computes **recall@k, precision@k, MRR, NDCG@k, hit_rate@k**
  (`metrics/retrieval_metrics.py`).
- The ranker is **injected** (`RankFn = (question, scope) -> list[str]`), so the *same* harness scores
  the trivial baseline today and real `HybridRetriever` later — no change to the runner. This is the
  seam the reranker plugs into in Phase 3.5 (see [`retrieval/phase-3.5.md`](./retrieval/phase-3.5.md)).
- **Datasets** (`evaluation/datasets/`): `retrieval_smoke.json` (relevance), `permission.json`
  (isolation / no-leak), `ambiguity.json`. Today's gold set is **12 synthetic cases**; a real-ticket
  set is a Phase 5 deliverable.
- **`make eval`** (`run_baseline.py`) runs a naive manifest-order ranker and writes JSON + Markdown to
  `eval-reports/`. It exists **to be beaten** — it's the honest floor.

A dataset case looks like this (`datasets/retrieval_smoke.json`):

```json
{ "id": "rs-01",
  "question": "How do I request access to core systems when I join?",
  "relevant_chunk_ids": ["1001"],
  "scope": "100",
  "kind": "retrieval" }
```

---

## 9. A full worked example (end to end)

Using the real fixture page **1001 "Onboarding Guide"** (`tests/fixtures/confluence/page-1001.json`,
space `100`, version 3) and eval case **rs-01**.

### 9.1 Ingestion

The page's storage HTML has sections: *Getting Access*, *Development Environment*, *Key Contacts*,
*Troubleshooting → SSO login fails / VPN drops*. Ingestion produces roughly:

```
document_version (page 1001, cf_version 3, state=active)
└── chunk kind=0 PARENT  "Onboarding Guide > Getting Access"           (context unit, not embedded)
    ├── chunk kind=1 CHILD   display="Request access to the core systems via the IT portal…"
    │                        retrieval="Onboarding Guide — Getting Access\n
    │                                   <1-2 sentence context>\n\nRequest access to the core systems…"
    │                        embedding=[3072 floats]   tsv=to_tsvector(title+heading+text)
    │                        is_active=true  space_id=100  parent_chunk_id → the PARENT above
    └── … more children …
└── chunk kind=0 PARENT  "Onboarding Guide > Troubleshooting > SSO login fails"
    └── chunk kind=1 CHILD   "Clear your browser cache and retry. If it persists, contact #it-support."
```

`page_source[1001].active_doc_version_id` points at this version; the previous version (if any) is
`superseded` and retained for rollback.

### 9.2 Retrieval

Question: *"How do I request access to core systems when I join?"*, scope `"100"`.

1. Embed the question → query vector.
2. Dense search returns children near it (the *Getting Access* child ranks high); keyword search
   matches on `access`, `core`, `systems`.
3. RRF fuses both lists; page **1001** surfaces at the top.
4. Scope `"100"` is a space scope → page 1001 (space 100) is visible → kept.
5. Return `["1001", …]`.

### 9.3 Evaluation

The case's `relevant_chunk_ids` is `["1001"]`. Since `1001` is rank 1, this case scores
**MRR = 1.0, recall@5 = 1.0, hit_rate@5 = 1.0**. Averaged across all 12 cases, that's the retrieval
baseline `make eval` reports.

### 9.4 What the answer runtime adds on top (Phase 4, shipped)

The same retrieval, then: rerank the survivors with a cross-encoder → expand each winning child to
its **parent** text → send parents to the answer model → generate a grounded answer with a numbered
citation to page 1001's *Getting Access* section → stream it over `POST /chat` to the widget UI. See
[`retrieval/phase-4.md`](./retrieval/phase-4.md) for the full pipeline and PLAN.md's live-verification
notes for the actual browser round trip this was checked against.

---

## 10. What the PLAN adds (3.5 → 9)

Sections 1–9 above are **TODAY**: `PLAN.md`'s accuracy + multi-source security + real-chatbot layer
is built on top of the original Phase 1–3 pipeline without rebuilding what already worked (RRF,
parent/child chunking, contextual retrieval, versioning are all kept as originally designed). The
target pipeline from the original plan is now the **as-shipped** one:

```
scope → conversational rewrite → embed → (RLS-scoped) dense ∥ keyword → RRF
      → permission filter → cross-encoder rerank(≤75 → k) → parent-context expansion
      → grounded generation w/ forced citations → refusal threshold → one CRAG retry → SSE stream
```

**Two layered security controls** (both always apply): source-level **RLS** (3.5) isolates whole
source systems; page-level **principal ACL** (4) enforces per-page read restrictions. RLS is the
security net; an explicit `WHERE source_id = ANY(:sources)` is added alongside it for recall +
planner-friendliness.

The full per-phase breakdown of what each PLAN item changed, where, and its exact status now lives
in the two phase folders instead of one table here — see
[`ingestion/README.md`](./ingestion/README.md) for the write-path phases (1, 2, 3.5's tagging/
scoping half, 4.6's Confluence/attachment fixes, 6) and
[`retrieval/README.md`](./retrieval/README.md) for the read/answer-path phases (0, 3, 3.5's
reranker/RLS-reader half, 4, 4.6's chat/permission fixes, 5, 7, 9).

---

## 11. How to evaluate "are we doing the right thing?"

Use this doc as the reference and check each claim against reality:

- **Ingestion correctness** — `make check` (401 backend tests). Chunk sizes/overlap match
  [`ingestion/phase-2.md`](./ingestion/phase-2.md)'s chunking rules? Re-embed reuse fires only when
  config is unchanged?
- **Atomicity** — is the live corpus ever half-rebuilt? (It shouldn't be — §6. `is_active` flips in
  the activation transaction.)
- **Retrieval quality** — `make eval`. Does real `HybridRetriever` beat the naive baseline? Does the
  report show **rerank lift** (Precision@5 / NDCG@10 before vs after) now that reranking
  ([`retrieval/phase-3.5.md`](./retrieval/phase-3.5.md)) runs?
- **Isolation** — a query scoped to `confluence:default` returns rows; a **wrong** `source_id`
  returns **zero** (RLS default-deny); the reader role cannot see unscoped rows and fails closed
  outside an offline env if misconfigured (PLAN 4.6.10).
- **Groundedness** — does every answer carry a citation to a real chunk
  ([`retrieval/phase-4.md`](./retrieval/phase-4.md))? Does refusal fire when nothing is relevant,
  instead of hallucinating?
- **The gate** — from `apps/automation`, `make check` (boundaries + `pytest -q`) stays green and, from
  the repo root, `make boundaries` exits 0 on every change.

If any of the above disagrees with what this doc says, the doc (or the code) is wrong — file it, and
fix whichever drifted. Keep this file's banner, data model, and worked example current; keep the
phase-by-phase claims current in `ingestion/` and `retrieval/` instead (root `CLAUDE.md`).

---

## 12. Confluence source scoping — implemented (PLAN 3.5.6)

**Moved.** The full write-up — the `source_scope` table, `scope_resolver.py`, its reconciliation
wiring, and the two deviations from the original design — now lives in
[`ingestion/phase-3.5.md`](./ingestion/phase-3.5.md). Decision history and the status ledger stay in
`docs/rag/PLAN.md` §0.

---

### Anchor index (for quick verification)

This table is a fast file-path lookup, not a narrative — for what each file *does* and why, follow
the phase links in [`ingestion/`](./ingestion/README.md) / [`retrieval/`](./retrieval/README.md).

| Concept | File |
|---|---|
| App wiring, gateway choice, scheduler, chat router mount | `app/main.py` |
| The 11 tables + indexes | `app/platform/db/models.py` |
| Webhook + security controls | `app/features/confluence_sync/server/webhook.py` |
| Job queue (claim/complete/fail/reap) | `app/platform/jobs/queue.py` |
| Worker 3-transaction discipline | `app/features/confluence_sync/application/worker.py` |
| Change classification + sync outcome | `app/features/confluence_sync/application/sync_service.py` |
| Chunk sizing + keys | `app/features/ingestion/domain/chunking.py` |
| Contextual retrieval | `app/features/ingestion/application/contextualizer.py` |
| Versioning / activation / rollback | `app/features/ingestion/application/versioning.py` |
| Hybrid retriever (dense ∥ keyword → RRF → permission → rerank) | `app/features/retrieval/application/retriever.py` |
| Dense + keyword SQL | `app/features/retrieval/infrastructure/search_repo.py` |
| RRF | `app/features/retrieval/domain/fusion.py` |
| Permission policy (real, DB-backed since 4.3) | `app/features/retrieval/domain/permission.py` |
| Reranker client (Cohere / Fake) | `app/platform/clients/reranker_client.py` |
| Answer runtime (rewrite → CRAG → refusal → expand → generate → cite) | `app/features/rag_agent/application/answer_service.py` |
| Refusal threshold | `app/features/rag_agent/domain/refusal.py` |
| Citation enforcement | `app/features/rag_agent/domain/citations.py` |
| Chat HTTP surface (`POST /chat`, feedback) | `app/features/rag_agent/server/router.py` |
| Answer caching (PLAN 5.2) | `app/features/rag_agent/application/answer_cache.py` |
| Eval runner + metrics | `app/features/evaluation/runner.py`, `metrics/retrieval_metrics.py` |
| All config | `app/platform/config/settings.py` |
| The upgrade plan + status ledger | `docs/rag/PLAN.md` |
| The design of record | `docs/rag/DESIGN.md` |
