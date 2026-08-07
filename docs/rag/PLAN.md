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

Fresh context: read this ledger + `docs/rag/DESIGN.md`, then do these **in order**:

1. **Add API keys to the root `.env`** (the user is providing these; do not invent them):
   - `RERANKER_API_KEY=<cohere key>` **and** `RERANKER_PROVIDER=cohere` — enables the real
     cross-encoder so 3.5.5 can measure an actual rerank lift. (Tests still force `fake` via
     `conftest.py`, so CI stays deterministic — no action needed there.)
   - Confirm already-present: `OPENAI_API_KEY` (embeddings, set), `ANTHROPIC_API_KEY`
     (contextualization + Phase-4 answers, set). `CONFLUENCE_API_TOKEN` is dead — needed only for
     *live* ingestion, not for offline 3.5/4.
2. **Run the pre-phase verification gate on Phase 3.5** (per `CLAUDE.local.md` rule 2): security of the
   reranker/embedding HTTP clients, real tests present, acceptance met. Record any gap here as a task.
3. **Do 3.5.5** — rerank-lift reporting in `features/evaluation`; with the live key, capture the real
   Precision@5 / NDCG@10 lift and set `refusal_min_rerank_score` from it. Then the **Phase 3.5 exit
   gate**, and `/compact-ultra` again before Phase 4.

**Supabase decision: deferred to Phase 5** (prod/deploy only; keep local Docker pgvector for dev).
When Phase 5 starts, ask for the connection string, confirm pgvector ≥ 0.8, and adapt the
`rag_reader`/RLS model to Supabase roles (`authenticated`/`service_role` + JWT-claim RLS).

### Progress (as of 2026-08-07, branch `feat/rag-phase-3.5`)

| Phase | Status | Commit | Proof |
|---|---|---|---|
| **0** — DESIGN.md + ADR-0004/0005 | ✅ done | `d793bb1` | design of record + 2 ADRs, code-grounded |
| **3.5.1** — pin pgvector 0.8 + HNSW iterative-scan GUCs | ✅ done | `7cd9fd1` | pgvector 0.8.5 pinned by digest; 4 unit tests |
| **3.5.2** — cross-encoder reranker (Cohere/Fake) + wire | ✅ done | `7cd9fd1` | 10 unit tests; rerank after permission filter; Fake in CI |
| **3.5.3** — provider tags + RLS + `rag_reader` role | ✅ done | `96f4786` | RLS default-deny proven; migration 0002 reversible |
| **3.5.4** — `query_trace` scoreboard (minimal) | ✅ done | `a9f9259` | 1 trace/retrieval; migration 0003 reversible |
| **3.5.5** — measure rerank lift + Phase 3.5 exit gate | ⏳ next | — | needs eval-harness work; real lift needs a live reranker key |
| **4** — answer runtime + chat (rag_agent, `POST /chat`) | ⬜ todo | — | HTTP+LLM surface → full security controls required |
| **5** — optimization & proof | ⬜ todo | — | Supabase, caching, red-team, latency/cost |

Gate at each ✅: `make check` green (116 tests, was 99), `make boundaries` clean, ruff/pyright at the
ADR-0003 D1 baseline (no regression). Reader/RLS isolation tests + both migrations verified.

### Deviations already taken (documented, not silent)

- **Source columns keep their `server_default`** (plan said "drop it"): keeps the migration-built and
  `create_all`-built schemas identical, and the sole inserter (`versioning.py`) stamps `source_id`
  explicitly anyway. Losing nothing on isolation — RLS enforces reads.
- **Writer stays the existing superuser `rag`** (no separate `rag_writer` owner): brownfield
  preservation; a superuser bypasses RLS, which is the required "writer bypasses RLS" property.

### Blockers / need from you  *(ask before doing dependent work)*

1. **Supabase vector store** — **DECIDED: Phase 5 (prod/deploy only)**; keep local Docker pgvector for
   dev now. When Phase 5 starts, I'll need: (a) the connection string (session-pooler or direct, port
   5432, `postgresql+psycopg://…`); (b) confirmation the instance runs **pgvector ≥ 0.8** (needed for
   `hnsw.iterative_scan`; Supabase may pin older); (c) how **`rag_reader` + RLS** maps onto Supabase
   roles (`authenticated`/`service_role`/`anon` + JWT-claim RLS). **Do not invent a connection string.**
2. **Reranker API key (Cohere)** — **needed next.** Add `RERANKER_API_KEY` + `RERANKER_PROVIDER=cohere`
   to `.env` so 3.5.5 measures a real rerank lift (CI stays on `FakeReranker`). Without it, 3.5.5 ships
   the lift *mechanism* but "after" == "before" offline, and `refusal_min_rerank_score` can't be tuned
   from real numbers.
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
| `refusal_min_rerank_score` | (tune in 3.5.5) | 4 | below → refuse + route to human |
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

### 3.5.5 Measure

**Task.** Extend `features/evaluation/run_baseline.py` / `runner.py` to report **rerank lift** —
Precision@5 and NDCG@10 **before vs after** rerank — while keeping the report format comparable to
the existing baseline. This is the phase's accuracy proof.

**Acceptance.** `make eval` prints a before/after table; the after-rerank numbers are the new
baseline. Use these numbers to set `refusal_min_rerank_score` for Phase 4.

**Phase 3.5 exit gate:** `make check` green, `make eval` shows rerank lift, isolation tests pass,
pgvector ≥ 0.8 confirmed, every retrieval traced. No-regression on ruff/pyright (ADR-0003 D1).

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
