# Plan — Omniboost RAG: accuracy-first upgrade + provider-tag multi-source spine

## Context

The Omniboost RAG backend (`apps/automation`) is offline-verified through Phase 3 (99 tests green,
eval reproduces baseline). A market research brief (naive RAG ~44% → advanced ~63% factual accuracy)
proposes ~13 upgrade layers. We audited every layer against the **actual code** (three exploration
passes + a design-validation pass) rather than the handover, and confirmed the running config
directly (`.env`: OpenAI `text-embedding-3-large`@3072, `RERANKER_PROVIDER=cohere` but **no reranker
code exists**).

**Why this change:** the user wants one backend + one corpus to power *multiple chatbots*, each
scoped by tag to a **source system** ("provider"), with a **hard security boundary** between
scopes, easy CRUD of data per source, and the latest accuracy techniques — **accuracy first, speed
second**. Reranking (absent today) is called out as essential for Confluence docs.

**Intended outcome:** a source-tagged, RLS-isolated, reranked, traced retrieval pipeline that is
measurably more accurate offline (Phase 3.5), then a grounded/cited streaming chatbot on top
(Phase 4), then optimization + proof (Phase 5). Phase 0 writes the governing design doc first.

### Product decisions (fixed by the user)
1. **"Provider" = source system** (Confluence now; Zendesk/Notion/uploads later). Many sources → one corpus; each bot scoped to a subset.
2. **Hard security boundary** between scopes → Postgres Row-Level Security + app checks. Default-deny.
3. **Confluence-only for now** → add source/tag columns + RLS + a clean seam; do **not** generalize the Confluence-specific ingestion/gateway yet.

## Current state — research vs. code (what NOT to rebuild)

**Already modern — keep:** parent/child chunking (`ingestion/domain/chunking.py`, `Chunk.parent_chunk_id`);
contextual retrieval (`ingestion/application/contextualizer.py`, prompt-cached); **RRF already implemented**
(`retrieval/domain/fusion.py` — research's "swap weighted-sum→RRF" is *done*); halfvec@3072 HNSW index;
immutable versioning + atomic activation + rollback + GC (`ingestion/application/versioning.py`);
3-pass re-embed reuse gate (`ingestion/domain/chunk_diff.py`); deterministic SQL filtering (no LLM filters);
custom eval harness with `RankFn` injection seam (`features/evaluation`).

**Gaps (map to the phases below):** no provider/source/tenant column anywhere (only Confluence `space_id`);
**no reranker at all** (dead `cohere` config); no `hnsw.iterative_scan`; no request tracing (structlog only);
no query rewrite / answer generation / citations / refusal / CRAG; principal ACL is fixture-only (DB stores
only an access-scope *hash*, not principal lists); `POST /chat` absent, web route is a real 501 stub; no caching;
gold set is 12 synthetic cases (no real-ticket set). Graph RAG stays off (research: cost/latency unjustified).

## Target architecture (one line)

`scope → conversational rewrite → embed → (RLS-scoped) dense ∥ keyword → RRF → permission filter →
cross-encoder rerank(75→k) → parent-context expansion → grounded generation w/ forced citations →
refusal threshold → one CRAG retry → SSE stream`, every request written to a `query_trace` row.

---

## Phase 0 — Design doc + ADRs (write first, no code)

Deliverable: **`apps/automation/docs/rag/DESIGN.md`** (or `docs/rag/DESIGN.md`) — the A-to-Z text the user
asked for: current pipeline, target pipeline, the provider-tag/RLS isolation model, the ingestion→retrieval→answer
flow, the accuracy stack, the eval/tracing scoreboard, config/flags, and a table mapping each research layer to
keep/upgrade/add/reject with rationale. Plus ADRs in `docs/adr/`:
- **ADR-0004 — Multi-source provider tagging + Row-Level Security isolation.**
- **ADR-0005 — Reranking + the answer pipeline (cross-encoder only; forced citations; refusal; one CRAG retry).**

Gate: user review of DESIGN.md before Phase 3.5 code.

---

## Phase 3.5 — Accuracy + tagging spine (offline-measurable, no chat)

Every item is verifiable against `retrieval_smoke.json` / `permission.json` via `test_retrieval_eval.py`.
**Do the sub-steps in this order — the first two are hidden dependencies.**

### 3.5.1 Pin pgvector ≥ 0.8 + enable iterative scan  *(must be first)*
- `infra/foundation/docker-compose.yml`: pin `pgvector/pgvector:pg16` → a **0.8.x** digest/tag (rolling tag today).
- Retrieval sets per-transaction: `SET LOCAL hnsw.iterative_scan = 'relaxed_order'` and `SET LOCAL hnsw.ef_search = 100`.
- Rationale: RLS narrow-scoping silently over-filters HNSW (returns < LIMIT); iterative scan is the safety valve. `relaxed_order` is fine because we re-rank downstream.

### 3.5.2 Reranker (the user's priority) — text-fetch refactor THEN wire in
- New `Reranker` Protocol (mirror `EmbeddingProvider` in `platform/clients/embeddings_client.py:43`), new `platform/clients/reranker_client.py`: `CohereReranker` (raw httpx, `POST /v2/rerank`, `rerank-v3.5`, same timeout/retry/breaker/abuse-cap discipline as `anthropic_client.py`), `FakeReranker` (identity), `build_reranker(settings, client)` factory with offline fallback. Export both from `platform/clients/__init__.py`. Add `RerankError`.
- **Data-flow change (not a config flip):** add `fetch_rerank_texts(session, page_ids) -> {page_id: text}` to `search_repo.py` (DISTINCT ON page_id, `left(title||retrieval_content, 4000)`) — the retriever deals in page ids only today and reranking needs text.
- Wire into `HybridRetriever.retrieve` (`retrieval/application/retriever.py`) **after the permission filter, before the top-k slice**: never rerank a doc the principal can't see. Bump `candidate_k` 40→**60–75**, add `rerank_depth=75`, feed survivors, return `k=5`.
- Hard rule (ADR-0005): purpose-built cross-encoders only — **no general-LLM rerankers**.
- Force `reranker_provider=fake` in the test settings fixture (`.env` has a live Cohere key; offline fallback only fires on an *empty* key → tests would hit Cohere non-deterministically).

### 3.5.3 Provider tagging + RLS + reader role  *(ship atomically with the eval-harness update)*
- Schema: add `source_type String(32)`, `source_id String(128)`, `tags ARRAY(Text)` to **`page_source` and `chunk`** (not `document_version` — retrieval never reads it). `source_id` (e.g. `confluence:default`) is the isolation key; `source_type` is a coarse label (String+CHECK, **not** a PG enum — avoids `ALTER TYPE` friction as connectors grow).
- Migration (first real one, `down_revision="0001_core_schema"`): add NOT NULL cols with `server_default` (backfills existing Confluence rows), then drop the DB default so ingestion must set `source_id` explicitly. Add `ix_chunk_active_source (is_active, source_id)`.
- Ingestion writes `source_id="confluence:default"` at the single activation point (the clean seam: a constant now, a parameter when a 2nd source lands).
- **RLS on `chunk`:** `ENABLE` + `FORCE ROW LEVEL SECURITY`; `CREATE POLICY chunk_source_read FOR SELECT USING (source_id = ANY(string_to_array(current_setting('app.allowed_sources', true), ',')))`. Unset GUC → NULL → **default-deny**.
- **Role split** (`platform/db/engine.py`): keep the existing engine/`session_scope()` as **`rag_writer`** (`BYPASSRLS`) — worker/webhook/reconcile untouched. Add `get_reader_engine()`/`get_reader_sessionmaker()` on a new `database_reader_url` (**`rag_reader`**, scoped, non-owner). `HybridRetriever` uses the reader sessionmaker.
- Retrieval scoping (`retriever.py`): at txn start, `session.execute(text("SELECT set_config('app.allowed_sources', :s, true)"), {"s": ",".join(allowed_sources)})` — **`set_config`, not `SET LOCAL` (the latter can't bind params)**.
- **Belt-and-suspenders recall:** ALSO add explicit `AND source_id = ANY(:sources)` to `_base_filters()` in `search_repo.py` so the planner uses `ix_chunk_active_source`. RLS = security net; explicit WHERE = correctness/recall.
- **Eval harness update (same PR):** `test_retrieval_eval.py` builds the retriever as the writer today; switching to the reader makes it RLS-subject → 0 rows unless it sets `app.allowed_sources` to the fixture `source_id`. Add role creation (or a scoped-reader path) to the test DB harness (`confluence_sync/tests/conftest.py` pattern) and add a **negative isolation test** (wrong `source_id` → empty result).

### 3.5.4 Request tracing scoreboard
- New `QueryTrace` ORM model + migration (`query_trace` table), written via the **writer** engine (so RLS never blocks trace inserts and feedback can `UPDATE` later). Populate retrieval fields now (raw query, retrieved page/chunk ids, rerank scores, `allowed_sources` as an isolation audit, embedding/reranker model, latency); leave `rewritten_query`/`answer`/`citations`/`feedback` nullable for Phase 4.
- structlog stays for ops logging; Langfuse remains an optional future exporter.

### 3.5.5 Measure
- Extend `run_baseline` / eval to report **rerank lift** (Precision@5, NDCG@10 before/after rerank) and keep report format comparable. This is the accuracy proof for the phase.

---

## Phase 4 — Answer runtime + chat (the actual chatbot)

- **Conversational query rewrite** (multi-turn → standalone), one cheap LLM call, always on (`routing_model`). Store `rewritten_query` in the trace.
- **Answer generation as a FIXED workflow** (not an agent loop; research + repo standard): rewrite → RLS-scoped retrieve → RRF → rerank → **parent-context expansion** (join `parent_chunk_id`, feed parent text) → grounded generation with **forced numbered citations** (uncited claims stripped) → **refusal threshold** (top rerank score < cutoff → "not in the docs" + route to human) → **one CRAG corrective retry** (cap at 1 — protects p95).
- New **`rag_agent` feature** behind its own public root (per repo standard); export the answer service.
- **Real principal ACL storage** — replace the fixture-backed `PrincipalPermissionPolicy`: persist principal lists (not just the access-scope hash) queryable, enforce PRE-search alongside RLS. (Source-level RLS from 3.5 and page-level principal ACL are distinct layers — both apply.)
- **`POST /chat` SSE** endpoint in `app.main` (start/token/citations/done), wired to the **reader** engine (must not be wired before 3.5's reader+RLS exist). Apply `securing-http-and-llm-endpoints` (HTTP + LLM surface).
- **Web chat UI:** flesh out the existing `apps/web/src/features/chat` scaffold — SSE parsing in `api/chat-client.ts`, streaming/history/citation cards in `ui/`, `.env.local` (`NEXT_PUBLIC_API_BASE_URL`); replace the `/api/chat` 501 with the real SSE proxy; publish the chat contract in `packages/contracts`. Add a thumbs up/down → `PATCH /chat/{trace_id}/feedback` (updates `query_trace.feedback`).

## Phase 5 — Optimization & proof

- **Embedder bake-off** on the (now real) gold set: OpenAI-3072 incumbent vs Voyage-3.x vs Qwen3-8B vs bge-m3 (multi-provider code already exists); commit one, re-embed via the version-stamp gate. Consider Matryoshka/dim reduction + `chunk-level` rerank (Option B).
- **Caching:** exact-match (Redis) + **semantic cache with per-`source_id`/scope keys + TTL** + keep prompt caching. Redis only if the proportionality gate is met.
- **Adaptive router (last):** classify query difficulty → simple vs decompose; optional HyDE / multi-query (RAG-fusion) for hard queries only.
- **Proof:** config sweeps, prompt-injection + permission/isolation red-team, measured latency (TTFT p50<1.5s/p95<2.5s, e2e p95<10s) + cost, deploy/rollback runbooks (`docs/runbooks/`). Optional: fine-tune embedder on real ticket pairs. Graph RAG stays off.

---

## Master-handover integration

Update `.compact-ultra/MASTER-HANDOVER.md` (Phase 0 task): insert **Phase 3.5** into the §A.1 table and §E,
correct the two verified inaccuracies (embedder is env-driven OpenAI-3072 not a code default; the reranker is
**not** staged — no client exists), and revise Phase 4/5 scope to reference the new `rag_agent` feature,
RLS spine, and `query_trace`. Add ADR-0004/0005 to §C.

## Critical files
- `apps/automation/app/platform/db/models.py` — new cols on `page_source`+`chunk`, `QueryTrace`, `ix_chunk_active_source`.
- `apps/automation/alembic/versions/` — new migration (cols + backfill + RLS DDL + `query_trace`), `down_revision="0001_core_schema"`.
- `apps/automation/app/platform/db/engine.py` — reader engine/sessionmaker (role split).
- `apps/automation/app/features/retrieval/infrastructure/search_repo.py` — source WHERE, `fetch_rerank_texts`, iterative-scan GUCs.
- `apps/automation/app/features/retrieval/application/retriever.py` — `set_config` scoping, rerank insertion, depth 75.
- `apps/automation/app/platform/clients/reranker_client.py` (new) + `platform/clients/__init__.py` exports; template: `embeddings_client.py`.
- `apps/automation/app/platform/config/settings.py` — `database_reader_url`, rerank/rewrite/refusal knobs; test fixture forces `reranker_provider=fake`.
- `apps/automation/app/features/confluence_sync/tests/conftest.py` + `.../test_retrieval_eval.py` — reader role + isolation tests.
- `infra/foundation/docker-compose.yml` — pin pgvector 0.8; add `rag_writer`/`rag_reader` roles (init SQL).
- Phase 4: new `apps/automation/app/features/rag_agent/`, `app.main` `POST /chat`, `apps/web/src/features/chat/*`, `packages/contracts`.

## Verification
- **Gate unchanged:** from `apps/automation`, `make check` (boundaries + `pytest -q`) stays green; `make boundaries` exit 0.
- **Isolation:** new tests — a query scoped to `confluence:default` returns rows; a wrong `source_id` returns **zero** (RLS default-deny); reader role cannot see unscoped rows.
- **Reranker:** eval reports Precision@5 / NDCG@10 **lift** vs no-rerank on `retrieval_smoke.json`; deterministic with `FakeReranker` in CI.
- **pgvector:** confirm server ≥0.8 (`SELECT extversion FROM pg_extension WHERE extname='vector'`); confirm iterative scan returns full `LIMIT` under a narrow `source_id` scope.
- **Tracing:** each retrieval writes a `query_trace` row with retrieved ids + rerank scores + `allowed_sources`.
- **Phase 4 e2e:** ask a question in the web UI → streamed, grounded, correctly-cited answer scoped to permitted sources; refusal fires below threshold; feedback updates the trace row.
- **No-regression:** ruff/pyright held at baseline (ADR-0003 D1); OpenAPI/collect deltas only where intended.

## Top risks (from design validation)
1. pgvector not pinned to 0.8 → iterative scan missing → RLS silently over-filters (looks like a reranker regression). **Pin first.**
2. RLS as sole recall path → must pair with explicit `WHERE source_id = ANY(:sources)` + iterative scan.
3. `SET LOCAL` can't bind params → use `set_config(..., true)`; wrong = injection or silent default-deny.
4. Eval harness runs as writer → RLS untested or broken; bundle harness+roles with the RLS PR.
5. Reranker needs text the retriever doesn't have → `fetch_rerank_texts` refactor precedes wiring.
6. `.env` live Cohere key in `env=local` → force `fake` reranker in tests for determinism.
7. Owner bypasses RLS → reads must run as non-owner `rag_reader`; writer is `BYPASSRLS`.
