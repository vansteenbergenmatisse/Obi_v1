# Omniboost Confluence RAG — Master Handover

**Status date:** 2026-08-07
**Supersedes:** the 2026-08-06 read-only-audit edition. The architecture work that edition
proposed in its §C/§D (reconcile the standard, enforce feature public surfaces, relocate
`hashing`, align the version, update `FEATURES.md`) is now **executed and committed** — see
§C/§D below, which record the applied result rather than a plan. Env inventory (§B),
remaining feature phases (§E), and preserved engineering context (§G) carry forward intact.
Where anything disagrees with this document or the live codebase, **the verified code wins.**
**Repo:** `…/Downloads/AGENTIC WORKLFOWS/OMNIBOOST/RAG-TOAST-omniboost`.

> The architecture-conformance refactor ran as a fixed 8-phase plan on `main`, gated
> green-to-green after every phase. Baseline tags: `pre-refactor-baseline` (red bisect
> anchor), `green-baseline` (first trustworthy green). Decisions recorded in **ADR-0003**;
> the governing project standard is the new root **`CLAUDE.md`**.

---

## A. Current Project Status

### A.1 Confirmed current phase
**Feature phases 1–3 complete and offline-verified. The architecture-conformance refactor is
complete. Phase 4 (RAG agent + chat UI) has not started.** The root `README.md` is stale — trust
this doc and the code.

| Phase | Scope | Status |
|---|---|---|
| 1 — Audit & baseline | Scaffold, pg16+pgvector, migration 0001, eval harness, fixtures, baseline | ✅ Complete |
| 2 — Confluence sync & versioning | REST client, webhook, job queue+worker, reconciliation, immutable versions + atomic activation + rollback | ✅ Complete |
| 3 — Accuracy-first ingestion & retrieval | Tokenization, parent/child chunking, embeddings client, contextual retrieval, 3-pass reuse diff, attachment extraction, re-embed gate, permission-aware hybrid retriever | ✅ Complete (offline/Fake-provider verified) |
| **Architecture conformance** | Feature/platform/shared public surfaces, machine-enforced boundaries, `hashing`→`shared`, version single-source, ADR-0003, root `CLAUDE.md` | ✅ **Complete** |
| 4 — RAG agent & chat UI | Orchestration agent, cross-encoder rerank, real ACL storage, Next.js chat UI, `/api/chat` | ❌ Not started (`apps/web/.../api/chat` is a 501 stub) |
| 5 — Optimization & proof | Config sweeps, rerank-lift, prompt-injection tests, measured latency/cost, caching, runbooks | ❌ Not started |

### A.2 What is complete (this refactor)
- **Feature public surfaces, enforced.** All four features (`confluence_sync`, `ingestion`,
  `retrieval`, `evaluation`) and the `platform/clients` capability expose one public
  `__init__.py` root; every external consumer imports through it. Zero external deep-imports remain.
- **Boundaries are machine-checked.** `apps/automation/tools/check_feature_boundaries.py`
  (stdlib `ast`, catches function-local imports) enforces four rules Ruff cannot; wired as
  `make boundaries` and `make check`. Verified against planted violations of every rule.
- **`shared/` exists; `hashing` relocated there** from the `platform/` root. Backend uses
  `app/{features, platform, shared}`; `components/` is UI-only (frontend). The two-standards
  conflict is resolved in ADR-0003 and the root `CLAUDE.md`.
- **Version single-sourced** at `app/__init__.py::__version__` (0.2.0); pyproject reads it via
  Hatchling dynamic version, `app.main` stamps FastAPI. The 0.1.0/0.2.0 drift is gone.
- **Hermetic test settings.** The `settings` fixture no longer depends on the on-disk `.env`
  (old debt #2), so the suite is a stable **99 passed** regardless of `.env` contents.
- **7-table versioned store** with atomic activation, rollback, HNSW-over-`halfvec` for 3072-dim
  vectors (ADR-0002). **Eval beats baseline** (retrieval_smoke mrr 0.75→1.00, ndcg 0.82→1.00;
  permission: no cross-scope leak).

### A.3 Live credential verification (from the 2026-08-06 audit)
| Credential | Result | Note |
|---|---|---|
| `OPENAI_API_KEY` | ✅ **LIVE** | Real `text-embedding-3-large` returned a 3072-dim vector. |
| `ANTHROPIC_API_KEY` | ✅ **LIVE** | Key valid. |
| `RERANKER_API_KEY` (Cohere) | ✅ **LIVE** | `rerank-v3.5` works; staged for Phase 4, not yet consumed. |
| `CONFLUENCE_API_TOKEN` | ❌ **BLOCKED** | 403 "caller cannot access Confluence"; account has **no Confluence seat**. A fresh token alone will not fix it — see §B.3. |

### A.4 Known bugs, risks, debt (current)
Resolved by this refactor: feature public surfaces (was debt #3), version mismatch (#5), loose
`hashing.py` (#7), test/`.env` coupling (#2), the two-standards conflict (old §C.1 / assumption
#11), and stale bytecode caches (#6, cleared in Phase 0).

Still open:
1. **[CONFIG] Stray `CONFLUENCE_WEBHOOK_SECRET=changeme` in root `.env`.** No longer breaks tests
   (the hermetic fixture strips it), but empty it before enabling live webhooks.
2. **[RISK] Everything Phase-3 was verified on the *Fake* embedding provider + *fixture* corpus.**
   No real page has ever been embedded or retrieved. First real ingest is the true test (blocked
   on Confluence).
3. **[RISK] Permission/ACL is policy-layer only**, backed by fixture restrictions. **Real ACL
   storage is a Phase-4 item** — do not treat current filtering as production access control.
4. **[SECURITY] Keys pasted into chat** (OpenAI, Anthropic, Cohere, Confluence) live in the
   transcript — **rotate all four** once wired.
5. **[DEBT] Ruff/Pyright baseline dirt** (Ruff 2 errors / 25 unformatted, Pyright 31/1) predates
   this standard and is tracked at no-regression (ADR-0003 D1), not yet cleaned.
6. **[DEBT] A few empty placeholder dirs** may remain (e.g. `docs/architecture/`,
   `docs/runbooks/`); fill or leave untracked — runbooks are a Phase-5 deliverable.

---

## B. Environment Setup

### B.1 Required `.env` files
| File | Exists? | Purpose | When |
|---|---|---|---|
| **Root `./.env`** | ✅ yes (single source of truth) | All automation secrets + config. Loaded by `settings.py` via `env_file=(".env","../../.env")`. | Now |
| **`./.env.example`** | ✅ yes | Committed placeholder template. Keep in sync; never real secrets. | Now |
| **Test env** | Hermetic `Settings(...)` fixture + `omniboost_rag_test` DB via conftest | No longer reads the real `.env`. | Now |
| **`apps/web/.env.local`** | ❌ not yet | Frontend runtime config (API base URL, public flags). | **Phase 4** |
| **Staging / production env** | ❌ not yet | Same var set as root `.env`, injected by host / secrets manager. Supabase `DATABASE_URL`. | Phase 5 / deploy |

> There is **one** `.env` (root). The former `apps/automation/.env` was consolidated and deleted.
> Do not recreate a second `.env` under `apps/automation/` — it would shadow the root file.

### B.2 Environment-variable inventory
Legend — **Scope:** server-only unless marked *public*. **Phase:** earliest phase that needs it.

| Variable | Service | Why required | Phase | Current status |
|---|---|---|---|---|
| `CONFLUENCE_BASE_URL` | Confluence | Locate wiki REST v2 (`{base}/api/v2`); must include `/wiki` | 2 | ✅ set |
| `CONFLUENCE_EMAIL` | Confluence | Basic-auth identity | 2 | ✅ set (switch to service account, §B.3) |
| `CONFLUENCE_API_TOKEN` | Confluence | Basic-auth token | 2 | ❌ **DEAD** — replace via service account |
| `CONFLUENCE_SPACES` | Confluence | Which spaces to index (`ENG,PRODUCT`) | 2 | ❌ **EMPTY** |
| `CONFLUENCE_WEBHOOK_SECRET` | Confluence | HMAC-verify inbound webhooks | 2 (live webhooks) | ⚠️ stray `changeme` — empty until webhooks used |
| `CONFLUENCE_SERVICE_ACCOUNT_ID` | Confluence | Self-event detection | 2 (webhooks) | empty |
| `ANTHROPIC_API_KEY` | Anthropic | Contextualization now; answers in P4 | 3 | ✅ **LIVE** (rotate) |
| `ROUTING_MODEL` | Anthropic | Routing + per-chunk contextualization | 3 | ✅ `claude-haiku-4-5-…` |
| `ANSWER_MODEL` | Anthropic | Grounded answer synthesis | 4 | ✅ `claude-sonnet-5` |
| `EMBEDDING_PROVIDER` / `_MODEL` / `_DIM` | OpenAI | Provider/model/vector width; DIM must match the halfvec index | 3 | ✅ `openai` / `text-embedding-3-large` / `3072` |
| `OPENAI_API_KEY` | OpenAI | Real embeddings | 3 | ✅ **LIVE** (rotate) |
| `EMBEDDING_TIMEOUT_SECONDS` / `_MAX_BATCH` / `_MAX_RETRIES` / `_BREAKER_THRESHOLD` / `_MAX_TEXTS_PER_CALL` | — | LLM-call controls | 3 | ✅ sane defaults |
| `CONTEXTUALIZATION_ENABLED` / `_TIMEOUT_SECONDS` / `_MAX_RETRIES` / `_MAX_DOC_CHARS` | — | Contextual-retrieval controls | 3 | ✅ |
| `RERANKER_PROVIDER` / `_API_KEY` / `_LOCAL_MODEL` | Cohere | Rerank (staged for P4) | 4 | ✅ `cohere` LIVE (staged, rotate) |
| `DATABASE_URL` | Postgres/pgvector | DB connection | 1 | ✅ local `:5434` |
| `EVIDENCE_TOKEN_BUDGET` / `PROVIDER_TIMEOUT_SECONDS` | — | Retrieval budgets | 3/4 | ✅ |
| `LIGHTWEIGHT_RECON_CRON` / `COMPLETE_RECON_INTERVAL_DAYS` | — | Reconciliation schedule | 2 | ✅ |
| `LOG_LEVEL` / `ENV` | — | Runtime | 1 | ✅ |
| *(future)* `NEXT_PUBLIC_API_BASE_URL`, auth vars | Frontend | Chat UI → `/api/chat`; user identity → access scope | 4 | ❌ not created |

### B.3 Credentials you still must provide
1. **Confluence — a service account, not a personal login.** The 403 is because the account behind
   the token has **no Confluence seat**. Create/invite a dedicated account (e.g.
   `confluence-rag@omniboost.com`) at `admin.atlassian.com`, grant it **Confluence product access**
   + **read** on the target spaces, log in as it, create a **classic API token** (`id.atlassian.com`
   → *Create API token*, not "with scopes"), and send the token + `CONFLUENCE_EMAIL`. The
   `accountId` becomes `CONFLUENCE_SERVICE_ACCOUNT_ID`.
2. **`CONFLUENCE_SPACES`** — pick the space keys to index.
3. **(Live webhooks only)** `CONFLUENCE_WEBHOOK_SECRET` — invent a random string, mirror it in
   Confluence's webhook config. Skip if relying on scheduled reconciliation.
4. **Rotate** the four keys already pasted into chat once wired.

### B.4 Supabase for Postgres + pgvector — appropriate, no code change
Supabase **is** managed PostgreSQL with pgvector; repoint `DATABASE_URL` and nothing else changes.
It is *not* a separate vector database (which the standard forbids) — same engine, hosted.
- `DATABASE_URL` → Supabase **session pooler** or **direct** connection on **port 5432** (not the
  `:6543` transaction pooler — Alembic migrations need session/direct). Keep the
  `postgresql+psycopg://` prefix.
- One-time: in the SQL editor run `create extension if not exists vector;` and confirm
  **pgvector ≥ 0.7.0** (needed for the `halfvec` 3072-dim index).
- **Not needed**: `SUPABASE_URL` / `_ANON_KEY` / `_SERVICE_ROLE_KEY` (only for PostgREST/JS SDK/
  Auth/Storage, which this app does not use).

---

## C. Architecture Standard (resolved — ADR-0003)

The two competing standards are reconciled. The governing document is the repo-root **`CLAUDE.md`**;
the decision and its register live in **`docs/adr/0003-Feature-Boundary-Enforcement.md`**.

- **Backend uses three of the five folders:** `app/{features, platform, shared}`. `components/` is
  UI-only and belongs to `apps/web`; it is not a backend folder.
- **`features/`** — business capabilities, each behind one public `__init__.py` root.
- **`platform/`** — technical capabilities (db, clients, config, jobs, logging). `platform/db` is
  imported by full path (a large namespaced ORM vocabulary), not through a facade (ADR-0003 D5).
- **`shared/`** — stable cross-feature primitives with no clearer owner (currently `hashing`).
- **Enforcement:** the four import rules are checked by `tools/check_feature_boundaries.py` and
  gated in `make check`. Add a needed symbol to the feature's `__init__.py`; never deep-import
  across a boundary.

## D. Restructuring — completed

Executed green-to-green on `main`; each step is one atomic commit gated by pytest + boundaries +
no-regression on Ruff/Pyright. What the prior edition listed as §D plan is done:

| Item | Result |
|---|---|
| Feature public surfaces (`__init__.py` exports) | ✅ 4 features + `platform/clients` faceted; all consumers routed through roots |
| Machine-enforced boundaries | ✅ `tools/check_feature_boundaries.py` + `make boundaries`/`make check` |
| Relocate `hashing.py` | ✅ moved to `app/shared/hashing.py`; importers updated |
| Align package version | ✅ single-sourced at `app/__init__.py` (0.2.0), pyproject dynamic |
| `FEATURES.md` public-surface fields | ✅ updated to the real `__all__` per feature |
| Hermetic test settings | ✅ fixture independent of `.env`; 99 passed |
| Standard reconciliation + ADR | ✅ root `CLAUDE.md` + ADR-0003 |

**Verification (every phase):** `pytest -q` = 99 passed; `import app.main` clean (no cycle);
`tools/check_feature_boundaries.py` exit 0; `pytest --collect-only` and OpenAPI byte-identical to
baseline (OpenAPI `info.version` unchanged at 0.2.0); `app.*` startup graph = 46 modules; Ruff
2 errors / 25 unformatted and Pyright 31/1 held flat (no-regression, ADR-0003 D1).

---

## E. Remaining Implementation Phases

### Phase 4 — RAG agent & basic chatbot
- **Objective:** Typed orchestration agent + Next.js chat UI; streaming, grounded, cited answers.
- **Dependencies:** Phase 3 (✅) + architecture conformance (✅); live Confluence + first real ingest.
- **Env:** `ANSWER_MODEL`, `ROUTING_MODEL` (live), `RERANKER_PROVIDER=cohere` + `RERANKER_API_KEY`
  (staged), `EVIDENCE_TOKEN_BUDGET`, `PROVIDER_TIMEOUT_SECONDS`; new `apps/web/.env.local`
  (`NEXT_PUBLIC_API_BASE_URL`, auth vars).
- **Tasks:** auth/scope → conversation state → ambiguity/clarify → query rewrite → routing → hybrid
  retrieval → RRF → **cross-encoder rerank** (wire the staged Cohere/local path) → parent-context
  expansion → evidence check → one corrective-retrieval cycle → grounded generation → citation
  validation → streaming; **real ACL storage** (replace the fixture-backed policy layer); `apps/web`
  chat UI (streaming, history, citation cards, dev trace); replace the `/api/chat` **501 stub** +
  validate inbound `ChatRequest`; publish the chat contract in `packages/contracts`.
  New backend work is a **`rag_agent` feature** behind its own public root, per the standard.
- **Testing:** agent step units; SSE parsing / partial + aborted streams; citation rendering; ACL
  enforcement on real storage; grounding/no-hallucination checks; endpoint security per
  `securing-http-and-llm-endpoints` (HTTP + LLM surface).
- **Completion:** a user asks a question in the UI and gets a streamed, grounded, correctly-cited
  answer scoped to their permissions, over **real** embeddings and **real** Confluence content.

### Phase 5 — Optimization & proof
- **Objective:** Prove accuracy; hit latency/cost targets; harden.
- **Tasks:** embedding/chunking/contextualization config sweeps; measure **reranking lift**; tune
  accuracy-before-latency; **prompt-injection + permission red-team**; full E2E; measured latency
  (TTFT p50 < 1.5s / p95 < 2.5s, e2e p95 < 10s, retrieval p95 < 1.5s) and cost; caching (Redis
  **only if** a real cache/queue/lock need is confirmed — proportionality gate); **deploy/rollback
  runbooks** (`docs/runbooks/`).
- **Completion:** documented accuracy lift, targets met with evidence, injection/permission tests
  pass, runbooks exist.

### Phase 6 (proposed — not in the original 5-phase plan)
Production hardening & operations: managed deploy (Supabase + host), secrets manager + key
rotation, CI/CD (ruff/pyright/pytest/boundaries + migrations gate), monitoring/alerting/tracing,
backup & DR for the versioned store, cost dashboards, service-account/permissions review.

---

## F. Prioritized Execution Checklist

Owner tags: **[YOU]** · **[AGENT]** · **[BLOCKED]** waiting on info/credential.

### 1. Credentials & environment
- [ ] **[YOU]** Create Confluence **service account**, assign a **seat**, grant read on target spaces. *(BLOCKED: org-admin rights)*
- [ ] **[YOU]** Generate a **classic API token** as that account; send token + email.
- [ ] **[YOU]** Choose `CONFLUENCE_SPACES`.
- [ ] **[YOU]** (optional) Invent `CONFLUENCE_WEBHOOK_SECRET` if using live webhooks.
- [ ] **[YOU]** Decide Supabase now or later; if now, send the session-pooler `DATABASE_URL` + password.
- [ ] **[AGENT]** Empty the stray `CONFLUENCE_WEBHOOK_SECRET`; fetch `CONFLUENCE_SERVICE_ACCOUNT_ID`; re-run live tests. *(BLOCKED on token)*
- [ ] **[YOU]** Rotate the four keys pasted into chat once wired.

### 2. Architecture — DONE
- [x] **[AGENT]** Reconcile the standard; author root `CLAUDE.md`; write **ADR-0003**.
- [x] **[AGENT]** Enforce feature public surfaces; add the boundary checker; relocate `hashing`; align the version; update `FEATURES.md`.

### 3. Build & regression testing
- [x] **[AGENT]** 99 green; boundaries pass; Ruff/Pyright held at no-regression; eval beats baseline.
- [ ] **[YOU/AGENT]** **First real ingest** of 1–2 live pages; verify chunks/embeddings/citations/retrieval. *(BLOCKED on Confluence)*

### 4. Phase 4 — RAG agent & chat UI (per §E)
### 5. Phase 5 — Optimization & proof (per §E)
### 6. Phase 6 — Production hardening (proposed; confirm scope first)

**Do not start Phase 4 until the first real ingest is verified (needs live Confluence).**

---

## G. Preserved Engineering Context

Kept because it prevents re-breaking solved problems.

### G.1 Phase-2 engineering decisions (do not undo without reason)
- **`Document.page_id` FK is `DEFERRABLE INITIALLY DEFERRED`.** `page_source ⇄ document_version ⇄
  document` form an insert-order cycle; the registry row is written last in `stage_and_activate`, so
  a non-deferrable FK violates on **every first index**. Flows into migration `0001` via
  `create_all`. **Do not revert to a plain FK.**
- **Finish + verify a phase before stacking the next.** Applies before Phase 4.
- **`FixtureConfluenceGateway` lives in `app/` (not `tests/`) with a LAZY loader import.**
  `main.py`'s offline path needs it, but the fixture corpus is a test artifact not shipped in the
  wheel; a top-level `import tests…` would break `import app.main` in production. Falls back to the
  base page file when a per-version snapshot is absent (only page 1001 has snapshots). **Keep it lazy.**
- **Test-DB harness redirects the whole app engine at `omniboost_rag_test`** (env `DATABASE_URL` +
  `lru_cache` clear), scoped to `confluence_sync/tests`, autouse-truncate per test. The worker uses
  its own `session_scope`, so injecting sessions is not enough.
- **Worker uses 3 separate transactions:** claim (commit) → handle+complete (one tx) → fail (own tx).
  A shared claim+handler tx would roll back the attempts/lease increment on handler error → infinite
  retry with no backoff. Safe because handlers are idempotent + version-guarded. **Preserve the split.**
- **`confluence_sync/application/worker.py` lazily imports `reconciliation` inside a function** to
  break a module-load cycle. It is a legal same-feature deep import (boundary rule b). **Do not hoist it.**

### G.2 Known operational gotcha — stale dev DB
The **dev** database `omniboost_rag` (not the test DB) may still carry the **old non-deferrable FK**;
a first real index would fail there until rebuilt. The test DB is auto-rebuilt each pytest run.
**Before the first real ingest**, rebuild the dev DB: `make down && make up && make migrate`.

### G.3 Rejected paths (do not redo)
- Extending Mewsy_v2 (Node/Express flat-markdown) — can't meet pgvector/hybrid/event-sync.
- Non-deferrable `document.page_id` FK — breaks first index.
- Requiring a per-version snapshot for every fixture page — only 1001 has them; fall back to base file.
- Postgres on `:5433` — port taken by `guided-setup-pg`; use **`:5434`** (`omniboost_rag_pg`).
- Faceting `platform/db` — large namespaced vocabulary; import by full path (ADR-0003 D5).
- Renaming `app/` → `src/` — breaks hatch/pyright/pytest/uvicorn/alembic (Brownfield Preservation).
- Reformatting the 25 pre-existing Ruff-dirty files — out of scope; no-regression only (ADR-0003 D1).

### G.4 Run commands (reference)
```
pg:         make up                                   # omniboost_rag_pg, :5434
migrate:    make migrate                              # cd apps/automation && alembic upgrade head
test:       make test        (or: cd apps/automation && uv run pytest -q)   # 99 passed
boundaries: make boundaries  (or: cd apps/automation && uv run python tools/check_feature_boundaries.py)
gate:       make check                                # boundaries + tests
lint/types: cd apps/automation && uv run ruff check . && uv run pyright     # no-regression (2 / 31+1)
eval:       make eval                                 # python -m app.features.evaluation.run_baseline
serve:      uvicorn app.main:app                      # enable_background_jobs=true for scheduler+worker
web:        make web-dev                              # pnpm --filter web dev ; build: pnpm --filter web build
stack:      Python 3.12 (uv at apps/automation/.venv, dev extra: `uv sync --extra dev`) · pnpm 10 · Postgres 16 + pgvector ≥0.8
ports:      :5434 = ours (use) · :5433 = guided-setup-pg (avoid)
```

### G.5 Re-verification checklist (from a clean context)
1. Gates: `make check` (boundaries + 99 green) and `uv run python -c "import app.main"` clean.
2. Re-run the eval and **eyeball the rankings** (not just pass/fail): right page ranks first; no
   restricted page appears for an unauthorized scope.
3. Independent **spec-vs-impl + security review** of the diff, focusing on the atomic version swap +
   re-embed release gate (data-loss / mixed-version risk), the **two LLM-CALL surfaces** (OpenAI
   embeddings + Anthropic contextualization) against the `security_baseline` in `FEATURES.md`, and
   permission filtering (policy-layer today — real ACL storage is Phase 4).
4. **First real ingest is the real test:** once the Confluence service account is live, index 1–2
   real pages, check chunks/embeddings/citations/retrieval, then re-run the eval against **real
   OpenAI embeddings** (Phase 3 was proven on the Fake provider + keyword path only).
