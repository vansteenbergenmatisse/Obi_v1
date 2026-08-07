# Plan — Omniboost RAG: accuracy-first upgrade + provider-tag multi-source spine

> Full, execution-ready plan. Every task names its target file and symbol, the DDL/signature
> it introduces, and the check that proves it done. Grounded in a direct read of the running
> code (Aug 2026), not the handover. Do the phases in order; within Phase 3.5 do the sub-steps
> in the numbered order — the first two are hidden dependencies of the rest.

---

## 0. Status ledger & blockers  *(keep current — update after every phase)*

**Working rules (see local `CLAUDE.local.md`):** stop after **every** phase/sub-step so the user can
`/compact-ultra` (keep context < ~200k); before starting a new phase, **verify the previous one** —
security (HTTP/LLM controls), real tests, acceptance actually met — and if it falls short, add the
fix here as the next task; update this ledger after each phase.

### ▶ Resume here (after `/compact-ultra`) — first things first

**Phase 3.5 is COMPLETE (all sub-steps ✅, exit gate MET). Next is Phase 4.** The 3.5.5 work is
**committed** (`1b6e94c`) and the pre-Phase-4 verification gate has been **re-run and PASSED**
(2026-08-07, see below) — Phase 3.5 is solid to build on.

Fresh context: read this ledger + `docs/rag/DESIGN.md` (esp. §5 Proof of lift), then:

1. **Begin Phase 4** — answer runtime + chat (`rag_agent`, `POST /chat`). This is the first HTTP+LLM
   surface: invoke `securing-http-and-llm-endpoints` and apply the full control set (rule 2). Reuse the
   3.5 reader-engine + RLS scoping; refusal uses `refusal_min_rerank_score` (0.10 provisional).

**Pre-Phase-4 verification gate — re-run 2026-08-07, PASS:** pgvector 0.8.5 (≥ 0.8); `make boundaries`
clean; `make test` → **120 passed, 0 skipped**; the four DB-backed isolation/trace/lift tests
(`test_rls_default_deny_on_reader_role`, `test_retriever_wrong_source_scope_returns_zero`,
`test_retrieval_writes_one_query_trace_row`, `test_rerank_lift_before_vs_after`) all ran and passed;
all three migrations carry a `downgrade`; RLS `set_config` uses a bound `:s` param (injection-safe);
reranker has timeout/retry/breaker/abuse-cap and never logs the key; ruff 2 errors / 22 unformatted
(≤ 2/25) and pyright 31/1 — at the ADR-0003 D1 baseline, no regression.

**3.5.5 outcome (done):** rerank-lift mechanism (`evaluate_rerank_lift`, pure) + DB-backed integration
run captured a live Cohere lift of **ndcg@10 −0.123 / precision@5 +0.000** on the saturated 6-case fixture
— expected (no headroom); genuine lift deferred to the Phase-5 gold set. `refusal_min_rerank_score=0.10`
provisional. Keys confirmed present in `.env`: `RERANKER_PROVIDER=cohere` + `RERANKER_API_KEY`,
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`. `CONFLUENCE_API_TOKEN` still dead (live ingestion only).

**Supabase decision: its own dedicated Phase 6** (prod/deploy only; keep local Docker pgvector for
dev). See "Phase 6 — Supabase vector store migration & deploy" below; it's blocked on the user for the
connection string, a pgvector ≥ 0.8 confirmation, and the `rag_reader`/RLS→Supabase-roles mapping.

### Progress (as of 2026-08-07, branch `feat/rag-phase-3.5`)

| Phase | Status | Commit | Proof |
|---|---|---|---|
| **0** — DESIGN.md + ADR-0004/0005 | ✅ done | `d793bb1` | design of record + 2 ADRs, code-grounded |
| **3.5.1** — pin pgvector 0.8 + HNSW iterative-scan GUCs | ✅ done | `7cd9fd1` | pgvector 0.8.5 pinned by digest; 4 unit tests |
| **3.5.2** — cross-encoder reranker (Cohere/Fake) + wire | ✅ done | `7cd9fd1` | 10 unit tests; rerank after permission filter; Fake in CI |
| **3.5.3** — provider tags + RLS + `rag_reader` role | ✅ done | `96f4786` | RLS default-deny proven; migration 0002 reversible |
| **3.5.4** — `query_trace` scoreboard (minimal) | ✅ done | `a9f9259` | 1 trace/retrieval; migration 0003 reversible |
| **3.5.5** — measure rerank lift + Phase 3.5 exit gate | ✅ done | `1b6e94c` | 120 tests; `evaluate_rerank_lift` + live Cohere run; **lift −0.123 ndcg@10 on the saturated fixture — expected, real lift is a Phase-5 gold-set measurement** |
| **4** — answer runtime + chat (rag_agent, `POST /chat`) | ⏳ next | — | HTTP+LLM surface → full security controls required |
| **5** — optimization & proof | ⬜ todo | — | caching, adaptive routing, red-team, latency/cost |
| **6** — Supabase vector store migration & deploy | ⬜ todo (deferred) | — | prod target; needs connection string + pgvector ≥ 0.8 + role/RLS mapping |

Gate at each ✅: `make check` green (**120 tests**, was 116/99), `make boundaries` clean, ruff/pyright at the
ADR-0003 D1 baseline (no regression — 22/2 ruff ≤ 25/2, pyright 0/0 on touched files). Reader/RLS isolation
tests + both migrations verified.

**Phase 3.5 exit gate — MET (2026-08-07):** `make check` green (120); `make eval` prints the before/after
rerank table; isolation tests pass (RLS default-deny + wrong-source→0); pgvector 0.8.5 pinned; every
retrieval writes one `query_trace` row; no ruff/pyright regression. Rerank lift measured live (Cohere
`rerank-v3.5` + OpenAI-3072): **ndcg@10 −0.123, precision@5 +0.000 on `retrieval_smoke`** — the fixture is
already saturated (dense ranks the one relevant page first, before-ndcg = 1.000), so there is no headroom;
the genuine lift is a **Phase-5 gold-set measurement**. `refusal_min_rerank_score = 0.10` provisional,
re-tune in Phase 5. **→ ready for Phase 4 after `/compact-ultra`.**

### Deviations already taken (documented, not silent)

- **Source columns keep their `server_default`** (plan said "drop it"): keeps the migration-built and
  `create_all`-built schemas identical, and the sole inserter (`versioning.py`) stamps `source_id`
  explicitly anyway. Losing nothing on isolation — RLS enforces reads.
- **Writer stays the existing superuser `rag`** (no separate `rag_writer` owner): brownfield
  preservation; a superuser bypasses RLS, which is the required "writer bypasses RLS" property.

### Blockers / need from you  *(ask before doing dependent work)*

1. **Supabase vector store** — **DECIDED: its own Phase 6 (prod/deploy only)**; keep local Docker
   pgvector for dev now. When Phase 6 starts, I'll need: (a) the connection string (session-pooler or
   direct, port 5432, `postgresql+psycopg://…`); (b) confirmation the instance runs **pgvector ≥ 0.8**
   (needed for `hnsw.iterative_scan`; Supabase may pin older); (c) how **`rag_reader` + RLS** maps onto
   Supabase roles (`authenticated`/`service_role`/`anon` + JWT-claim RLS). **Never invent a DSN.**
2. **Reranker API key (Cohere)** — ✅ **PROVIDED & USED (2026-08-07).** `.env` carries
   `RERANKER_PROVIDER=cohere` + a live `RERANKER_API_KEY`; 3.5.5 measured a real lift with it (see the
   exit-gate note above). CI still forces `FakeReranker` via `conftest.py`, so the suite stays
   deterministic. No further action.
3. **Confluence token** — still dead (401/403, no Confluence seat; `CONFLUENCE_SPACES` empty). Blocks
   *live* ingestion only; all offline phases (3.5 → most of 4) run on the fixture corpus.
4. **Phase 5 infra (later)** — Redis for caching only if the proportionality gate is met; Langfuse
   optional. Will re-ask when Phase 5 starts.

---

## 1. Context

The Omniboost RAG backend (`apps/automation`) is offline-verified through Phase 3: **99 tests
green**, and `make eval` reproduces the retrieval baseline. A market-research brief (naive RAG
~44% → advanced RAG ~63% factual accuracy) proposes ~13 upgrade layers. Every layer was audited
against the **actual code** (three exploration passes + a design-validation pass), and the running
config was confirmed directly from `.env` and `settings.py`:

- Embeddings: OpenAI `text-embedding-3-large` @ **3072 dim** (env-driven; the code *default* is
  `voyage`, `.env` overrides to `openai`). Indexed as `halfvec(3072)` with an HNSW index.
- `reranker_provider` / `reranker_api_key` / `reranker_local_model` settings **fields exist**
  (`settings.py:62-65`, commented "used from Phase 4") but **no reranker client exists** — the
  config is dead. `.env` carries a live Cohere key.

**Why this change.** One backend + one corpus must power *multiple chatbots*, each scoped by tag to
a **source system** ("provider"), with a **hard security boundary** between scopes, easy per-source
CRUD, and the latest accuracy techniques. **Accuracy first, speed second.** Reranking (absent today)
is the user's called-out priority — essential for Confluence docs.

**Outcome.** A source-tagged, RLS-isolated, reranked, traced retrieval pipeline that is measurably
more accurate offline (Phase 3.5); then a grounded, cited, streaming chatbot on top (Phase 4); then
optimization + proof (Phase 5). Phase 0 writes the governing design doc first.

### 1.1 Product decisions (fixed by the user — do not relitigate)

1. **"Provider" = source system** (Confluence now; Zendesk / Notion / uploads later). Many sources →
   one corpus; each bot is scoped to a subset of sources.
2. **Hard security boundary** between scopes → Postgres Row-Level Security + application checks.
   **Default-deny.**
3. **Confluence-only for now** → add source/tag columns + RLS + a clean seam. Do **not** generalize
   the Confluence-specific ingestion/gateway yet; leave one activation point that takes a constant
   today and a parameter when a second source lands.

---

## 2. Current state — research vs. code (what NOT to rebuild)

**Already modern — keep as-is:**

| Capability | Where | Note |
|---|---|---|
| Parent/child chunking | `ingestion/domain/chunking.py`, `Chunk.parent_chunk_id` | parent expansion is a join away |
| Contextual retrieval | `ingestion/application/contextualizer.py` | prompt-cached |
| **RRF fusion** | `retrieval/domain/fusion.py` | research's "swap weighted-sum→RRF" is **done** |
| halfvec@3072 HNSW index | `models.py` `_HNSW_WHERE`, partial index | matches OpenAI-3072 |
| Immutable versioning + atomic activation + rollback + GC | `ingestion/application/versioning.py` | |
| 3-pass re-embed reuse gate | `ingestion/domain/chunk_diff.py` | avoids needless re-embeds |
| Deterministic SQL filtering (no LLM filters) | `search_repo.py` `_base_filters` | keeps recall honest |
| Custom eval harness + `RankFn` injection seam | `features/evaluation` | Precision@k / NDCG already computed |

**Gaps (each maps to a phase below):**

- No provider/source/tenant column anywhere — only Confluence `space_id`. → 3.5.3
- **No reranker at all** (dead `cohere` config). → 3.5.2
- No `hnsw.iterative_scan`; pgvector image is the rolling `pg16` tag (unpinned). → 3.5.1
- No request tracing (structlog only). → 3.5.4
- No query rewrite / answer generation / citations / refusal / CRAG. → Phase 4
- Principal ACL is fixture-only: the DB stores an access-scope *hash*, not principal lists. → Phase 4
- `POST /chat` absent; the web `/api/chat` route is a real 501 stub. → Phase 4
- No caching. → Phase 5
- Gold set is 12 synthetic cases; no real-ticket set. → Phase 5
- **Graph RAG stays off** (research: cost/latency unjustified for this corpus).

---

## 3. Target architecture (one line + expanded)

```
scope → conversational rewrite → embed → (RLS-scoped) dense ∥ keyword → RRF
      → permission filter → cross-encoder rerank(≤75 → k) → parent-context expansion
      → grounded generation w/ forced citations → refusal threshold → one CRAG retry → SSE stream
```

Every request writes one `query_trace` row (retrieval fields in 3.5; answer/feedback fields in 4).

Two layered security controls, both always applied:

- **Source-level RLS** (3.5): Postgres row-level security on `chunk`, keyed by `source_id`, enforced
  by a non-owner `rag_reader` role. Default-deny when the scope GUC is unset.
- **Page-level principal ACL** (4): persisted principal lists, enforced pre-search in the retriever.

---

## 4. Config & flags reference (single source of truth)

New / changed settings in `app/platform/config/settings.py` (add with safe defaults; document in
`.env.example`):

| Setting | Default | Introduced | Purpose |
|---|---|---|---|
| `database_reader_url` | `""` (falls back to `database_url` if empty) | 3.5.3 | non-owner `rag_reader` DSN for retrieval |
| `reranker_provider` | `""` → treat as `fake` offline | (exists) 3.5.2 | `cohere` \| `fake` \| `local` |
| `rerank_candidate_k` | `75` | 3.5.2 | candidates fetched before rerank |
| `rerank_depth` | `75` | 3.5.2 | max docs sent to the cross-encoder |
| `rerank_top_k` | `5` | 3.5.2 | survivors returned |
| `hnsw_ef_search` | `100` | 3.5.1 | per-txn recall knob |
| `hnsw_iterative_scan` | `relaxed_order` | 3.5.1 | safety valve under narrow RLS scope |
| `rewrite_enabled` | `true` | 4 | conversational query rewrite on |
| `refusal_min_rerank_score` | `0.10` provisional (set 3.5.5; re-tune Phase 5) | 4 | below → refuse + route to human |
| `crag_max_retries` | `1` | 4 | corrective retrieval cap (protects p95) |

**Test fixture rule (critical):** the hermetic settings fixture MUST force `reranker_provider=fake`.
`.env` carries a live Cohere key and `env=local`; the offline fallback only fires on an *empty* key,
so without this override CI would hit Cohere non-deterministically.

---

## Phase 0 — Design doc + ADRs (write first, no code)

**Goal.** Produce the A-to-Z governing document the user asked for, and lock the two decisions that
gate all Phase 3.5 code.

**Deliverables.**

- **`docs/rag/DESIGN.md`** — sections:
  1. Current pipeline (as-built, with file anchors).
  2. Target pipeline (the §3 diagram, expanded per stage).
  3. Provider-tag / RLS isolation model (roles, GUC, policy, default-deny proof).
  4. Ingestion → retrieval → answer data flow (end to end).
  5. The accuracy stack (rerank, parent expansion, citations, refusal, CRAG).
  6. Eval + tracing scoreboard (what `query_trace` captures; what eval reports).
  7. Config & flags (mirror §4).
  8. **Research-layer decision table** — each of the ~13 layers → keep / upgrade / add / reject +
     one-line rationale.
- **`docs/adr/0004-Multi-Source-Provider-Tagging-And-RLS.md`** — decision, context, the
  `source_type`/`source_id`/`tags` schema, RLS policy, role split, default-deny, consequences.
- **`docs/adr/0005-Reranking-And-Answer-Pipeline.md`** — cross-encoder-only rule (no general-LLM
  rerankers), forced citations, refusal threshold, one CRAG retry, why a fixed workflow not an agent
  loop.

**Order:** DESIGN.md before ADRs is fine, but the two ADR *decisions* must be settled before any
3.5 code.

**Gate.** User reviews `DESIGN.md` before Phase 3.5 code begins. No code in this phase.

---

## Phase 3.5 — Accuracy + tagging spine (offline-measurable, no chat)

Everything here is verifiable offline against `retrieval_smoke.json` / `permission.json` via
`test_retrieval_eval.py` and `make eval`. **Sub-steps run in this order.**

### 3.5.1 Pin pgvector ≥ 0.8 + enable iterative scan  *(must be first)*

**Why first.** RLS narrow-scoping silently over-filters HNSW (an ANN scan can return fewer than
`LIMIT` rows once the RLS predicate prunes the candidate set). `hnsw.iterative_scan` is the safety
valve — but it only exists in pgvector **0.8+**. If we ship RLS before pinning, recall drops and it
looks like a reranker regression.

**Tasks.**

1. `infra/foundation/docker-compose.yml`: change `image: pgvector/pgvector:pg16` → a pinned **0.8.x**
   tag/digest (the current tag is rolling). Record the exact digest in the compose file comment.
2. Add settings `hnsw_ef_search=100`, `hnsw_iterative_scan="relaxed_order"` (§4).
3. In the retrieval read transaction (added fully in 3.5.3's `retriever.py` work, but the GUC-setting
   helper lands here), issue per-transaction:
   `SET LOCAL hnsw.iterative_scan = 'relaxed_order'` and `SET LOCAL hnsw.ef_search = 100`.
   `relaxed_order` is acceptable because we re-rank downstream.

**Acceptance.**

- `SELECT extversion FROM pg_extension WHERE extname='vector'` returns **≥ 0.8**.
- Under a deliberately narrow `space_id`/`source_id` scope, dense search returns the full `LIMIT`
  (add a targeted test once 3.5.3 lands).

### 3.5.2 Reranker (the user's priority) — text-fetch refactor THEN wire in

**Design.** Mirror the embeddings abstraction exactly (`embeddings_client.py:43` `EmbeddingProvider`
Protocol + `_HttpEmbeddingProvider` machinery: timeout, bounded retry+backoff, circuit breaker,
abuse cap). Cross-encoder rerankers only — **no general-LLM rerankers** (ADR-0005).

**Tasks.**

1. **New `app/platform/clients/reranker_client.py`:**
   - `class RerankError(RuntimeError)`.
   - `@runtime_checkable class Reranker(Protocol)`: `model: str`; `rerank(query: str,
     docs: Sequence[tuple[int, str]], top_k: int) -> list[tuple[int, float]]` (returns
     `(page_id, score)` sorted desc).
   - `class CohereReranker` — raw `httpx`, `POST https://api.cohere.com/v2/rerank`, model
     `rerank-v3.5`, reusing the exact timeout / retry / breaker / abuse-cap discipline from
     `anthropic_client.py` / `_HttpEmbeddingProvider`.
   - `class FakeReranker` — identity: returns the input order, scores by descending input rank.
     Deterministic; used in tests and offline dev.
   - `def build_reranker(settings, client=None) -> Reranker` — factory with offline fallback:
     empty key **or** `provider in {"", "fake"}` **or** offline env → `FakeReranker`.
2. **Export** `Reranker`, `build_reranker`, `RerankError` from `app/platform/clients/__init__.py`.
3. **Data-flow refactor (not a config flip).** The retriever deals in **page ids only**; reranking
   needs text. Add to `search_repo.py`:
   ```python
   def fetch_rerank_texts(session, page_ids: Sequence[int]) -> dict[int, str]:
       # DISTINCT ON (page_id), left(title || ' ' || retrieval_content, 4000)
       # over active child chunks; subject to the same _base_filters + source scope.
   ```
4. **Wire into `HybridRetriever.retrieve`** (`retrieval/application/retriever.py:45`) **after the
   permission filter, before the top-k slice** — never rerank a doc the principal can't see:
   - Bump `candidate_k` default `40 → 75` (`rerank_candidate_k`).
   - After `allowed = [p for p in ranked if self._policy.allowed(p, scope)]`, fetch texts for the
     top `rerank_depth` allowed pages, call `self._reranker.rerank(query, docs, top_k=k)`, and
     return the reranked page ids as strings.
   - Inject the reranker via the constructor (`reranker: Reranker`), like `embedder`/`policy`.
5. **Test fixture:** force `reranker_provider=fake` in the hermetic settings fixture (§4 rule).

**Acceptance.**

- Deterministic in CI with `FakeReranker`.
- `make eval` reports **rerank lift**: Precision@5 and NDCG@10 before vs after rerank on
  `retrieval_smoke.json` (wired fully in 3.5.5).
- Feature boundaries stay clean (`make boundaries` exit 0): the retriever imports the reranker from
  `platform.clients` root, not a deep path.

### 3.5.3 Provider tagging + RLS + reader role  *(ship atomically with the eval-harness update)*

**Schema.** Add to **`page_source` and `chunk`** only (not `document_version` — retrieval never
reads it):

- `source_type String(32)` — coarse connector label. **String + CHECK constraint, not a PG enum**
  (avoids `ALTER TYPE` friction as connectors grow).
- `source_id String(128)` — the **isolation key**, e.g. `confluence:default`.
- `tags ARRAY(Text)` — free-form per-source tags for bot scoping.

**Migration** — the *first real* migration, `down_revision="0001_core_schema"`, in
`apps/automation/alembic/versions/`:

1. Add the three columns **NOT NULL with a `server_default`** so existing Confluence rows backfill
   (`source_id='confluence:default'`, `source_type='confluence'`, `tags='{}'`).
2. **Drop the server default afterward** so ingestion must set `source_id` explicitly going forward.
3. Add `Index("ix_chunk_active_source", "is_active", "source_id", postgresql_where=text("is_active"))`.
4. Add the CHECK constraint on `source_type`.
5. RLS DDL (raw SQL in the migration):
   ```sql
   ALTER TABLE chunk ENABLE ROW LEVEL SECURITY;
   ALTER TABLE chunk FORCE ROW LEVEL SECURITY;
   CREATE POLICY chunk_source_read ON chunk FOR SELECT
     USING (source_id = ANY(string_to_array(current_setting('app.allowed_sources', true), ',')));
   ```
   Unset GUC → `current_setting(..., true)` returns NULL → `string_to_array(NULL,...)` → no match →
   **default-deny**.

**ORM.** Reflect the three columns + the new index on `PageSource` (`models.py:85`) and `Chunk`
(`models.py:206`).

**Ingestion seam.** Write `source_id="confluence:default"` (and `source_type`, `tags`) at the
**single activation point** in `ingestion/application/versioning.py` (the atomic activation). A
constant today; a parameter when a second source lands.

**Role split** (`app/platform/db/engine.py`):

- Keep the existing `get_engine()` / `get_sessionmaker()` / `session_scope()` as the **`rag_writer`**
  path (owner, `BYPASSRLS`) — worker / webhook / reconcile untouched.
- Add `get_reader_engine()` / `get_reader_sessionmaker()` bound to `database_reader_url` as the
  **`rag_reader`** role (scoped, **non-owner**, no `BYPASSRLS`). `HybridRetriever` uses the reader
  sessionmaker. (Owner bypasses RLS — reads MUST run as the non-owner role.)
- `infra/foundation/docker-compose.yml`: add init SQL creating `rag_writer` (owner, BYPASSRLS) and
  `rag_reader` (login, non-owner, `GRANT SELECT` on the read tables).

**Retrieval scoping** (`retriever.py`): at transaction start, set the GUC with **`set_config`, not
`SET LOCAL`** (the latter can't bind parameters — using it here would be an injection vector or a
silent default-deny):
```python
session.execute(
    text("SELECT set_config('app.allowed_sources', :s, true)"),
    {"s": ",".join(allowed_sources)},
)
```
Plus set the 3.5.1 HNSW GUCs in the same transaction.

**Belt-and-suspenders recall** (`search_repo.py`): also add an explicit
`AND source_id = ANY(:sources)` to `_base_filters()` so the planner uses `ix_chunk_active_source`.
RLS is the *security net*; the explicit WHERE is *correctness + recall* (and lets the query planner
choose the source index).

**Eval-harness update (same PR — do not split).** `test_retrieval_eval.py` builds the retriever as
the **writer** today. Switching retrieval to the reader makes it RLS-subject → **0 rows** unless it
sets `app.allowed_sources` to the fixture `source_id`. So, in the same PR:

- Extend the test DB harness (`confluence_sync/tests/conftest.py` pattern) to create the `rag_reader`
  role (or expose a scoped-reader session) and set `app.allowed_sources` to the fixture source.
- Add a **negative isolation test**: a query scoped to a *wrong* `source_id` returns **zero** rows
  (RLS default-deny), and the reader role cannot see unscoped rows.

**Acceptance.**

- `make check` (boundaries + `pytest -q`) green; existing 99 tests still pass.
- Positive: query scoped to `confluence:default` returns rows.
- Negative: wrong `source_id` → zero rows; reader cannot see unscoped rows.
- Migration is reversible (`alembic downgrade -1` restores 0001 state).

### 3.5.4 Request tracing scoreboard

**Task.** New `QueryTrace` ORM model + migration (`query_trace` table), written via the **writer**
engine so RLS never blocks trace inserts and Phase-4 feedback can `UPDATE` the row later.

Columns populated **now** (retrieval): `id`, `raw_query`, `retrieved_page_ids`, `retrieved_chunk_ids`,
`rerank_scores`, `allowed_sources` (isolation audit), `embedding_model`, `reranker_model`,
`latency_ms`, `created_at`. Columns **nullable, filled in Phase 4**: `rewritten_query`, `answer`,
`citations`, `feedback`.

structlog stays for ops logging; Langfuse remains an optional future exporter (not built here).

**Acceptance.** Each retrieval writes one `query_trace` row carrying retrieved ids + rerank scores +
`allowed_sources`.

### 3.5.5 Measure ✅ done

**Task.** Extend `features/evaluation/run_baseline.py` / `runner.py` to report **rerank lift** —
Precision@5 and NDCG@10 **before vs after** rerank — while keeping the report format comparable to
the existing baseline. This is the phase's accuracy proof.

**What shipped.**
- `evaluate_rerank_lift(dataset, before_fn, after_fn, …)` + `RerankLiftReport` in `features/evaluation`
  (pure; exported from the feature root), computing precision@5 / ndcg@10 before/after + Δ.
- `run_baseline.py`: `write_rerank_lift_reports` + `_print_saved_rerank_lift`, so `make eval` echoes the
  saved before/after table (`eval-reports/rerank_lift.{json,md}`).
- The **real** before/after run is the DB-backed integration test `test_rerank_lift_before_vs_after`
  (reader role + RLS + indexed corpus): "before" = order-preserving `FakeReranker`, "after" =
  configured reranker. Writes the artifact under `EVAL_WRITE_RERANK_REPORT=1`.
- `refusal_min_rerank_score = 0.10` provisional setting (+ `.env.example`).
- Tests: 3 unit (`test_rerank_lift.py`: positive/zero/empty) + 1 integration → **120 tests green**.

**Measured (live Cohere `rerank-v3.5` + OpenAI-3072, 6-case `retrieval_smoke`):** precision@5
0.200→0.200 (+0.000); **ndcg@10 1.000→0.877 (−0.123)**. Negative *by construction*: dense already ranks
the one relevant page first (before-ndcg saturated at 1.000), so the cross-encoder has no headroom. The
genuine lift is a **Phase-5 gold-set measurement**; `refusal_min_rerank_score` re-tunes there. CI
(`FakeReranker`) → before == after → zero lift, deterministic.

**Acceptance.** ✅ `make eval` prints the before/after table (echoed from the saved artifact). The
threshold is set provisionally (0.10) pending the Phase-5 gold set — the fixture is too saturated to tune
it honestly.

**Phase 3.5 exit gate — MET (2026-08-07):** `make check` green (120), `make eval` shows the rerank table,
isolation tests pass, pgvector 0.8.5 pinned (≥ 0.8), every retrieval traced. No-regression on ruff/pyright
(ADR-0003 D1: 22/2 ruff ≤ 25/2; pyright 0/0 on touched files).

---

## Phase 4 — Answer runtime + chat (the actual chatbot)

**Goal.** A grounded, cited, streaming chatbot over the 3.5 spine. Fixed workflow, not an agent loop.

### 4.1 New `rag_agent` feature (own public root)

Create `app/features/rag_agent/` per the repo standard: one public `__init__.py` re-exporting the
answer service and its DTOs. Internal layout `application/` (orchestration), `domain/` (prompt
assembly, citation enforcement, refusal logic), `infrastructure/` (trace read/update, principal ACL
store). Add a `FEATURES.md` documenting the public boundary.

### 4.2 Answer workflow (fixed pipeline)

Order, each stage a plain function (research + repo standard — no agent loop):

1. **Conversational query rewrite** — multi-turn history → standalone query. One cheap LLM call
   (`routing_model`), always on (`rewrite_enabled`). Store `rewritten_query` in the trace.
2. **RLS-scoped retrieve → RRF → rerank** — reuse `HybridRetriever` (reader engine, scoped GUC).
3. **Parent-context expansion** — join `parent_chunk_id` and feed the *parent* chunk text to the
   generator (children retrieve, parents ground).
4. **Grounded generation with forced numbered citations** — every claim cites a retrieved chunk;
   **uncited claims are stripped** before returning.
5. **Refusal threshold** — if the top rerank score < `refusal_min_rerank_score`, refuse ("not in the
   docs") and route to a human instead of hallucinating.
6. **One CRAG corrective retry** — on a weak result, one corrective retrieval only
   (`crag_max_retries=1`) to protect p95.

### 4.3 Real principal ACL storage

Replace the fixture-backed `PrincipalPermissionPolicy` (`retrieval/domain/permission.py`): persist
**principal lists** (not just the access-scope hash), queryable, and enforce **pre-search** alongside
RLS. Source-level RLS (3.5) and page-level principal ACL (here) are distinct layers — **both apply**.

### 4.4 `POST /chat` SSE endpoint

In `app/main.py`, add `POST /chat` streaming SSE events `start` / `token` / `citations` / `done`,
wired to the **reader** engine (must not be wired before 3.5's reader+RLS exist). Add
`PATCH /chat/{trace_id}/feedback` (thumbs up/down → `UPDATE query_trace.feedback`, writer engine).
Apply the `securing-http-and-llm-endpoints` controls (this is both an HTTP and an LLM surface):
auth, rate limit, input validation, timeout/retry/breaker, output rate limit, PII redaction,
idempotency, audit logging, cost/abuse caps.

### 4.5 Web chat UI

Flesh out the existing `apps/web/src/features/chat` scaffold:

- `api/chat-client.ts` — SSE parsing.
- `ui/` — streaming message list, history, citation cards (scaffold files already exist:
  `message-list.tsx`, `chat-panel.tsx`, `composer.tsx`).
- `apps/web/src/app/api/chat/route.ts` — replace the 501 stub with the real SSE proxy to the backend.
- `.env.local` — `NEXT_PUBLIC_API_BASE_URL`.
- Publish the chat contract in `packages/contracts` (extend `src/openapi/chat.yaml` + `src/index.ts`).
- Thumbs up/down → `PATCH /chat/{trace_id}/feedback`.

**Phase 4 acceptance (e2e).** Ask a question in the web UI → a streamed, grounded, correctly-cited
answer scoped to the permitted sources; refusal fires below threshold; feedback updates the trace
row. `make check` green; boundaries clean; no-regression on ruff/pyright.

---

## Phase 5 — Optimization & proof

- **Embedder bake-off** on the (now real) gold set: OpenAI-3072 incumbent vs Voyage-3.x vs Qwen3-8B
  vs bge-m3 (multi-provider code already exists in `embeddings_client.py`). Commit one; re-embed via
  the version-stamp gate (`versioning.py`). Consider Matryoshka / dim reduction + chunk-level rerank.
- **Caching:** exact-match (Redis) + semantic cache keyed per `source_id`/scope + TTL; keep prompt
  caching. **Redis only if the proportionality gate is met** (confirmed cache/queue/lock need).
- **Adaptive router (last):** classify query difficulty → simple vs decompose; optional HyDE /
  multi-query (RAG-fusion) for hard queries only.
- **Proof:** config sweeps; prompt-injection + permission/isolation red-team; measured latency
  (TTFT p50 < 1.5s / p95 < 2.5s, e2e p95 < 10s) + cost; deploy/rollback runbooks in `docs/runbooks/`.
  Optional: fine-tune the embedder on real ticket pairs. **Graph RAG stays off.**

---

## Phase 6 — Supabase vector store migration & deploy  *(prod target; its own phase)*

**Goal.** Move the corpus + retrieval from local Docker pgvector to **Supabase** (managed Postgres +
pgvector) as the production vector store, preserving the ADR-0004 source-isolation model. Dev stays on
local pgvector until this phase. This is deploy/infra work, deliberately separated from the Phase 5
accuracy/optimization work so neither blocks the other.

**Blocked on the user (ask at phase start — never invent a DSN or key):**

- **Connection string** → `DATABASE_URL` (writer) and `DATABASE_READER_URL` (reader). Use the
  **session pooler or direct** connection (port 5432), **not** the `:6543` transaction pooler, so
  Alembic migrations + prepared statements work. Keep the `postgresql+psycopg://` prefix.
- **pgvector ≥ 0.8 confirmation.** Needed for `hnsw.iterative_scan` (the RLS-scope recall safety valve,
  3.5.1). Supabase may pin an older pgvector — if `< 0.8`, decide a mitigation before shipping RLS.
- **Role / RLS mapping.** Supabase manages roles differently (`authenticated` / `service_role` /
  `anon`, JWT-claim RLS, no plain superuser). Decide how `rag_reader` maps — since the app talks to
  Postgres directly (not PostgREST/JWT), a dedicated low-privilege Postgres role is the likely fit;
  the writer must retain a `BYPASSRLS`-equivalent path.

**Tasks.**

1. Enable pgvector on Supabase (`create extension if not exists vector;`); confirm version ≥ 0.8.
2. Repoint `DATABASE_URL` + `DATABASE_READER_URL` at Supabase; run `alembic upgrade head` there
   (0001 → 0003), confirming the halfvec/HNSW index and `query_trace` build.
3. Recreate roles + RLS on Supabase — the docker init SQL won't run there, so apply
   `schema.ensure_reader_role` + `schema.apply_chunk_rls` via a one-off script or a Supabase migration.
4. Load the corpus (re-embed via the version-stamp gate, or migrate rows).
5. Re-run the isolation tests + `make eval` against Supabase to confirm parity — RLS default-deny,
   rerank lift, and one `query_trace` row per retrieval all still hold.
6. Runbook in `docs/runbooks/`: pooler caveats, backup/restore, rollback, secret handling.

**Acceptance.** Isolation + eval pass against Supabase; `hnsw.iterative_scan` confirmed available (or a
documented mitigation); connection uses the psycopg driver; no secret in logs. `make check` still green
locally (dev unchanged).

---

## 5. Cross-cutting rules (apply in every phase)

- **Feature boundaries:** when other code needs a new symbol, export it from the feature/capability
  root (`__init__.py`) — never deep-import. `platform/**` and `shared/**` import no features. Run
  `make boundaries` before every commit.
- **No-regression on lint/type:** ruff/pyright held at the ADR-0003 D1 baseline (2/25 ruff, 31/1
  pyright). Bring files you touch clean; do not reformat files you didn't otherwise touch; do not let
  whole-repo counts rise.
- **Gate unchanged:** from `apps/automation`, `make check` (boundaries + `pytest -q`) stays green.
- **Migrations are reversible** and ordered from `0001_core_schema`.

---

## 6. Critical files

| File | Change | Phase |
|---|---|---|
| `docs/rag/DESIGN.md`, `docs/adr/0004*`, `docs/adr/0005*` | new design doc + ADRs | 0 |
| `infra/foundation/docker-compose.yml` | pin pgvector 0.8; add `rag_writer`/`rag_reader` init SQL | 3.5.1 / 3.5.3 |
| `app/platform/clients/reranker_client.py` (new) + `clients/__init__.py` | `Reranker`, `Cohere`/`Fake`, factory, exports | 3.5.2 |
| `app/features/retrieval/infrastructure/search_repo.py` | `fetch_rerank_texts`, source WHERE, HNSW GUCs | 3.5.1-3 |
| `app/features/retrieval/application/retriever.py` | `set_config` scoping, reader engine, rerank insertion | 3.5.2-3 |
| `app/platform/db/models.py` | `source_type`/`source_id`/`tags` on `page_source`+`chunk`; `ix_chunk_active_source`; `QueryTrace` | 3.5.3-4 |
| `apps/automation/alembic/versions/` (new) | cols + backfill + RLS DDL + `query_trace`; `down_revision="0001_core_schema"` | 3.5.3-4 |
| `app/platform/db/engine.py` | reader engine/sessionmaker (role split) | 3.5.3 |
| `app/platform/config/settings.py` | `database_reader_url`, rerank/rewrite/refusal knobs; fixture forces `reranker_provider=fake` | 3.5 |
| `confluence_sync/tests/conftest.py` + `test_retrieval_eval.py` | reader role + isolation tests | 3.5.3 |
| `features/evaluation/run_baseline.py` / `runner.py` | rerank-lift reporting | 3.5.5 |
| `app/features/rag_agent/` (new), `app/main.py` | answer workflow, `POST /chat`, `PATCH /chat/{id}/feedback` | 4 |
| `apps/web/src/features/chat/*`, `app/api/chat/route.ts`, `packages/contracts` | chat UI + SSE proxy + contract | 4 |

---

## 7. Verification (per gate)

- **Gate:** `make check` green; `make boundaries` exit 0.
- **Isolation:** scoped query returns rows; wrong `source_id` → zero (RLS default-deny); reader can't
  see unscoped rows.
- **Reranker:** `make eval` reports Precision@5 / NDCG@10 lift vs no-rerank; deterministic with
  `FakeReranker`.
- **pgvector:** `SELECT extversion FROM pg_extension WHERE extname='vector'` ≥ 0.8; iterative scan
  returns full `LIMIT` under a narrow scope.
- **Tracing:** each retrieval writes a `query_trace` row with retrieved ids + rerank scores +
  `allowed_sources`.
- **Phase 4 e2e:** web UI → streamed, grounded, cited, scoped answer; refusal below threshold;
  feedback updates the trace.
- **No-regression:** ruff/pyright at baseline; OpenAPI/collect deltas only where intended.

---

## 8. Risk register (from design validation)

1. **pgvector not pinned to 0.8** → iterative scan missing → RLS silently over-filters (reads like a
   reranker regression). **Pin first (3.5.1).**
2. **RLS as the sole recall path** → pair it with the explicit `WHERE source_id = ANY(:sources)` +
   iterative scan.
3. **`SET LOCAL` can't bind params** → use `set_config(..., true)`; the wrong choice is an injection
   vector or a silent default-deny.
4. **Eval harness runs as writer** → RLS untested or broken → bundle the harness + roles into the
   RLS PR (3.5.3), never split.
5. **Reranker needs text the retriever doesn't have** → the `fetch_rerank_texts` refactor precedes
   wiring (3.5.2).
6. **`.env` live Cohere key in `env=local`** → force `fake` reranker in tests for determinism.
7. **Owner bypasses RLS** → reads MUST run as the non-owner `rag_reader`; the writer is `BYPASSRLS`.
