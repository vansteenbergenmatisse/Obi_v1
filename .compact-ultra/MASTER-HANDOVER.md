# Omniboost Confluence RAG — Master Handover

**Status date:** 2026-08-06
**Consolidates and replaces:** the former `.compact-ultra/phase3-handover.md` (2026-08-03) and
`.compact-ultra/handover-20260728-153650.md` (2026-07-28), which have been **deleted** — all still-relevant
content (status, decisions, env, forward plan) is folded into this document, including the Phase-2 engineering
decisions and operational context now in **§G (Preserved Engineering Context)**. Only pure session narrative
(conversation digests, per-file "NEW/EDITED" annotations, diff summaries) was discarded. Where anything
disagrees with this document or the live codebase, **this document and the verified code win.**
**Repo:** `…/Downloads/AGENTIC WORKLFOWS/OMNIBOOST/RAG-TOAST-omniboost` (moved from the old
`~/Developer/omniboost-rag` path the older handover references).

> This handover was produced by a read-only audit: full code map, full doc synthesis, a live test run,
> and live authenticated calls to every credential. No code, env, or handover files were modified to
> produce it. Proposed changes in sections C–F are **plans awaiting your approval**, not applied work.

---

## A. Current Project Status

### A.1 Confirmed current phase
**Phases 1, 2, and 3 are complete and offline-verified. Phase 4 has not started.** The root `README.md`
is stale (still shows Phase 2 "in progress", Phase 3 "not implemented") — do not trust it; trust this doc.

| Phase | Scope | Status |
|---|---|---|
| 1 — Audit & baseline | Scaffold, pg16+pgvector, migration 0001, eval harness, fixtures, baseline | ✅ Complete |
| 2 — Confluence sync & versioning | REST client, webhook, job queue+worker, reconciliation, immutable versions + atomic activation + rollback | ✅ Complete |
| 3 — Accuracy-first ingestion & retrieval | Tokenization, parent/child chunking, embeddings client, contextual retrieval, 3-pass reuse diff, attachment extraction, re-embed gate, permission-aware hybrid retriever (dense∥keyword→RRF→permission) | ✅ Complete (offline/Fake-provider verified) |
| 4 — RAG agent & chat UI | Orchestration agent, cross-encoder rerank, real ACL storage, Next.js chat UI, `/api/chat` | ❌ Not started (`apps/web/.../api/chat` is a 501 stub) |
| 5 — Optimization & proof | Config sweeps, rerank-lift, prompt-injection tests, measured latency/cost, caching, runbooks | ❌ Not started |
| 6+ | **Not defined** — the plan contains exactly 5 phases. A proposed Phase 6 (production hardening) is in §E, clearly marked as *not in the original plan*. |

### A.2 What is complete (verified this audit)
- **Backend architecture is already feature-sliced and clean.** `apps/automation/app/` = `features/`
  (`confluence_sync`, `ingestion`, `retrieval`, `evaluation`) + `platform/` (clients, config, db, jobs,
  logging). Each feature carries `application / domain / infrastructure / schemas / server / tests`.
- **7-table versioned store** with atomic activation, rollback, HNSW-over-`halfvec` index for 3072-dim
  vectors (ADR-0002). One Alembic baseline migration `0001_core_schema`.
- **Eval harness** (DB-free): recall@k, MRR/nDCG, permission, latency. Phase-3 eval beats baseline
  (retrieval_smoke mrr 0.75→1.00, ndcg 0.82→1.00; permission: no cross-scope leak).
- **`ruff` clean; `import app.main` OK** (confirmed this audit).

### A.3 Live credential verification (NEW — supersedes the "MISSING/DEAD" table in older handovers)
Authenticated calls made 2026-08-06:

| Credential | Result | Note |
|---|---|---|
| `OPENAI_API_KEY` | ✅ **LIVE** | Real `text-embedding-3-large` returned a 3072-dim vector. Now present (older docs said MISSING). |
| `ANTHROPIC_API_KEY` | ✅ **LIVE** | Key valid. |
| `RERANKER_API_KEY` (Cohere) | ✅ **LIVE** | `rerank-v3.5` works. New since the docs; staged for Phase 4, not yet consumed by code. |
| `CONFLUENCE_API_TOKEN` | ❌ **BLOCKED** | 403 "caller cannot access Confluence"; same token 401s on Jira. Account has **no Confluence seat** — a fresh token alone will not fix it. See §B.3. |

### A.4 Known bugs, risks, assumptions, technical debt
1. **[BUG, introduced during env consolidation] Stray `CONFLUENCE_WEBHOOK_SECRET=changeme` in root `.env`.**
   The env consolidation left a placeholder value instead of empty. Because `test_unset_secret_fails_closed`
   reads the real `.env` via `get_settings()`, the non-empty secret sends the webhook down the HMAC path →
   **`1 failed, 98 passed`** right now. With the secret emptied it returns to **99 passed**. This is a config
   artifact, **not a code regression.** Fix = set `CONFLUENCE_WEBHOOK_SECRET=` (empty) — *awaiting your OK per
   your no-modify instruction.*
2. **[TEST HYGIENE] Tests are coupled to the real `.env`.** The `settings` fixture returns `get_settings()`,
   so suite pass/fail depends on `.env` contents. Fix: give the `settings` fixture a hermetic `Settings(...)`
   with explicit values, independent of the on-disk `.env`.
3. **[DEBT] Feature public surfaces not enforced.** Both `FEATURES.md` state "consumers deep-import today."
   The global standard wants each feature to expose one `__init__.py`/`index` public surface. Deferred in the
   older handover as a broad change. Real work for the §D restructuring.
4. **[DEBT] Empty placeholder directories** violate the project `.Claude/CLAUDE.md` "no placeholder folders"
   rule: `app/features/confluence_sync/domain/`, `app/features/ingestion/schemas/`, and the empty
   `docs/architecture/` + `docs/runbooks/` (runbooks are a Phase-5 deliverable).
5. **[DEBT] Version mismatch:** `app/main.py` declares `0.2.0`, `pyproject.toml` declares `0.1.0`.
6. **[DEBT] Stale bytecode:** `__pycache__` carries `co_filename` paths pointing at the old
   `~/Developer/omniboost-rag` location (project was copied with caches). Harmless but confusing in
   tracebacks. Fix: delete `__pycache__`/`.pytest_cache` or add to a clean step.
7. **[DEBT] `hashing.py` sits loose at `platform/` root** rather than in a named platform capability folder.
8. **[RISK] Everything Phase-3 was verified on the *Fake* embedding provider + *fixture* corpus.** No real
   page has ever been embedded or retrieved. First real ingest is the true test (blocked on Confluence).
9. **[RISK] Permission/ACL is policy-layer only**, backed by fixture restrictions. **Real ACL storage is a
   Phase-4 item** — do not treat current permission filtering as production access control.
10. **[SECURITY] Keys pasted into chat** (OpenAI, Anthropic, Cohere, Confluence) live in the transcript —
    **rotate all four** once wired.
11. **[ASSUMPTION] Two architecture standards coexist and disagree** — see §C.1. Must be reconciled before
    the §D restructuring.

---

## B. Environment Setup

### B.1 Required `.env` files
| File | Exists? | Purpose | When |
|---|---|---|---|
| **Root `./.env`** | ✅ yes (single source of truth after consolidation) | All automation secrets + config. Loaded by `settings.py` via `env_file=(".env","../../.env")`. | Now |
| **`./.env.example`** | ✅ yes | Committed placeholder template. Keep in sync; never put real secrets here. | Now |
| **Test env** | Uses root `.env` + `omniboost_rag_test` DB via conftest | Hermetic test settings recommended (debt #2). | Now |
| **`apps/web/.env.local`** | ❌ not yet | Frontend runtime config (API base URL, any public flags). `apps/web` currently reads **no** env vars. | **Phase 4** |
| **Staging / production env** | ❌ not yet | Same var set as root `.env`, values injected by the host / secrets manager (never committed). Supabase `DATABASE_URL`. | Phase 5 / deploy |

> Note: there is currently **one** `.env` (root). The former `apps/automation/.env` was consolidated into
> root and deleted. Do not recreate a second `.env` under `apps/automation/` — it would shadow the root file.

### B.2 Full environment-variable inventory
Legend — **Scope:** server-only unless marked *public*. **Phase:** earliest phase that needs it.
Secrets shown as placeholders only.

| Variable | Service | Why required | Used by | Scope | Phase | Where to obtain | Current status |
|---|---|---|---|---|---|---|---|
| `CONFLUENCE_BASE_URL` | Confluence | Locate wiki REST v2 (`{base}/api/v2`); must include `/wiki` | automation · confluence_client | server | 2 | Your Atlassian URL | ✅ set, correct |
| `CONFLUENCE_EMAIL` | Confluence | Basic-auth identity | automation · confluence_client | server | 2 | The (service) account | ✅ set (personal — switch to service account, §B.3) |
| `CONFLUENCE_API_TOKEN` | Confluence | Basic-auth token | automation · confluence_client | server | 2 | id.atlassian.com → API tokens | ❌ **DEAD/`<CONFLUENCE_API_TOKEN>`** — replace via service account |
| `CONFLUENCE_SPACES` | Confluence | Which spaces to index (`ENG,PRODUCT`) | automation · sync/reconciliation | server | 2 | You choose | ❌ **EMPTY** |
| `CONFLUENCE_WEBHOOK_SECRET` | Confluence | HMAC-verify inbound webhooks | automation · webhook | server | 2 (live webhooks only) | Invent; mirror in Confluence webhook config | ⚠️ **stray `changeme`** — should be empty until webhooks used (bug #1) |
| `CONFLUENCE_SERVICE_ACCOUNT_ID` | Confluence | Self-event detection | automation · event_service | server | 2 (webhooks) | `accountId` of service account (I can fetch once token is live) | empty |
| `ANTHROPIC_API_KEY` | Anthropic | Contextualization now; answers in P4 | automation · anthropic_client | server | 3 | console.anthropic.com | ✅ **LIVE** (rotate) |
| `ROUTING_MODEL` | Anthropic | Model for routing **+ per-chunk contextualization** | automation | server (config) | 3 | n/a (`claude-haiku-4-5-…`) | ✅ optimal |
| `ANSWER_MODEL` | Anthropic | Grounded answer synthesis | automation · rag agent | server (config) | 4 | n/a (`claude-sonnet-5`) | ✅ optimal |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` / `EMBEDDING_DIM` | OpenAI | Selects provider/model/vector width; DIM must match the built halfvec index | automation · ingestion | server (config) | 3 | n/a (`openai` / `text-embedding-3-large` / `3072`) | ✅ set |
| `OPENAI_API_KEY` | OpenAI | Real embeddings | automation · embeddings_client | server | 3 | platform.openai.com | ✅ **LIVE** (rotate) |
| `VOYAGE_API_KEY` | Voyage | Alt embedding provider | automation | server | — | voyageai.com | not needed (chose OpenAI) |
| `EMBEDDING_TIMEOUT_SECONDS` / `_MAX_BATCH` / `_MAX_RETRIES` / `_BREAKER_THRESHOLD` / `_MAX_TEXTS_PER_CALL` | — | LLM-call controls (timeout/retry/breaker/abuse cap) | automation · embeddings_client | server (config) | 3 | n/a | ✅ sane defaults |
| `CONTEXTUALIZATION_ENABLED` / `_TIMEOUT_SECONDS` / `_MAX_RETRIES` / `_MAX_DOC_CHARS` | — | Contextual-retrieval controls | automation · contextualizer | server (config) | 3 | n/a | ✅ |
| `RERANKER_PROVIDER` | Cohere | Selects reranker (`cohere` \| empty=local) | automation · retrieval (P4) | server (config) | 4 | n/a | ✅ `cohere` (staged) |
| `RERANKER_API_KEY` | Cohere | Hosted rerank | automation · retrieval (P4) | server | 4 | dashboard.cohere.com | ✅ **LIVE** (staged, not yet consumed; rotate) |
| `RERANKER_LOCAL_MODEL` | — | Local rerank fallback model | automation | server (config) | 4 | n/a (`BAAI/bge-reranker-base`) | ✅ |
| `DATABASE_URL` | Postgres/pgvector | DB connection | automation · db/engine, alembic | server | 1 | Local compose / Supabase (§B.4) | ✅ local `:5434` |
| `EVIDENCE_TOKEN_BUDGET` / `PROVIDER_TIMEOUT_SECONDS` | — | Retrieval budgets | automation · retrieval | server (config) | 3/4 | n/a | ✅ |
| `LIGHTWEIGHT_RECON_CRON` / `COMPLETE_RECON_INTERVAL_DAYS` | — | Reconciliation schedule | automation · scheduler | server (config) | 2 | n/a | ✅ |
| `LOG_LEVEL` / `ENV` | — | Runtime | automation | server (config) | 1 | n/a | ✅ |
| *(future)* `NEXT_PUBLIC_API_BASE_URL` | Frontend | Point chat UI at the automation `/api/chat` (or SSE proxy) | apps/web | **public** | 4 | You set per env | ❌ not created |
| *(future)* auth vars (e.g. `AUTH_*`) | Frontend/auth | User identity → retrieval access scope | apps/web + automation | mixed | 4 | TBD when auth is designed | ❌ not created |

### B.3 Credentials you still must provide (and how)
1. **Confluence — a service account, not your personal login.** The 403 is because the account behind the
   token has **no Confluence seat**; and a server must not depend on a personal account. Do:
   - Create/invite a dedicated account (e.g. `confluence-rag@omniboost.com`) at `admin.atlassian.com`.
   - Grant it **Confluence product access** (a seat) and **read permission** on the target spaces.
   - Log in **as that account**, create a **classic API token** (`id.atlassian.com` → *Create API token*,
     **not** "with scopes"), and give me the token + `CONFLUENCE_EMAIL`.
   - I will fetch its `accountId` for `CONFLUENCE_SERVICE_ACCOUNT_ID`.
   → sets `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`, `CONFLUENCE_SERVICE_ACCOUNT_ID`.
2. **`CONFLUENCE_SPACES`** — pick the space keys to index (the code from the space URL after `/spaces/`).
3. **(Live webhooks only)** `CONFLUENCE_WEBHOOK_SECRET` — invent a random string, mirror it in Confluence's
   webhook config. Skip if you rely on scheduled reconciliation.
4. **Rotate** the four keys already pasted into chat once everything is wired.

Everything else (OpenAI, Anthropic, Cohere, DB) is present and, where testable, live-verified.

### B.4 Supabase for Postgres + pgvector — is it appropriate? Yes.
Supabase **is** managed PostgreSQL with pgvector, so it fits the architecture with **no code change** — you
just repoint `DATABASE_URL`. It is *not* a separate vector database (which the global standard forbids); it's
the same engine, hosted.

**Exact Supabase variables needed: just one.**
- `DATABASE_URL` → the Supabase **session pooler** or **direct** connection on **port 5432** (not the `:6543`
  transaction pooler — Alembic migrations and prepared statements need session/direct). Keep the
  `postgresql+psycopg://` driver prefix. Form:
  `postgresql+psycopg://postgres.<project-ref>:<SUPABASE_DB_PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres`

**One-time setup:** in the Supabase SQL editor run `create extension if not exists vector;` and confirm
**pgvector ≥ 0.7.0** (required for the `halfvec` 3072-dim index; Supabase ships ≥0.8 on current projects).

**Not needed** for pgvector-over-Postgres: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
— those are only for the PostgREST/JS SDK/Storage/Auth features, which this app does not use. Add them **only
if** you later adopt Supabase Auth or Storage (a Phase-4/5 decision).

### B.5 Which variables per environment
- **Development:** root `.env`, local pg `:5434`, real keys (OpenAI/Anthropic/Cohere), Confluence via service
  account. `ENV=local`, `LOG_LEVEL=INFO`.
- **Test:** same var set; `DATABASE_URL` points at `omniboost_rag_test`; secrets should come from a hermetic
  fixture (debt #2), not the real `.env`. Embeddings run on the Fake provider.
- **Staging:** Supabase `DATABASE_URL`; real keys from the host/secrets manager; separate Confluence spaces
  or a staging space; webhooks optional.
- **Production:** Supabase `DATABASE_URL`; all secrets in a secrets manager (never committed); `ENV=production`
  (structlog JSON logs); live webhook secret; rotated keys; least-privilege service account.

---

## C. Architecture Work Before Phase 4

### C.1 The core decision to make first: reconcile TWO competing standards
There are two architecture standards in play and they disagree. **This must be resolved before restructuring.**
- **Global** `~/.claude/CLAUDE.md` — feature-shape backend: `features/<feature>/{application,domain,
  infrastructure,schemas,server,tests}` + `platform/` + repo-level `packages/{design-tokens,ui,contracts,
  config}`. **The current code already follows this.**
- **Project** `.Claude/CLAUDE.md` — requires every runnable app to have **five** folders:
  `app/ · features/ · components/ · platform/ · shared/`. The code does **not** have `components/` or
  `shared/` (backend has no UI; shared primitives live in `platform/`).

**Recommendation:** adopt the project `.Claude/CLAUDE.md` as the single governing standard, but amend it so
that `components/` is **UI-only (frontend apps)** and backend services may fold `shared/` into `platform/` or
add a thin `shared/` for pure primitives (e.g. `hashing.py`). This keeps the (good) existing backend structure
compliant with minimal churn and reserves the 5-folder shape for `apps/web`. *(Awaiting your call — this is
an ADR-worthy decision; I'll write ADR-0003 once you choose.)*

### C.2 Proposed additions to the `.claude` architecture instructions
The existing project `.Claude/CLAUDE.md` already defines: what a feature is, what a reusable component is, the
folder structure, public/private boundaries, dependency rules, placement order, and anti-patterns. It is
**missing** the following, which your brief explicitly asks for — proposed to add:
- **Naming conventions:** PascalCase files/folders for TS; `snake_case` for Python files and DB
  tables/columns (tables plural); components one default export matching filename; fixed suffixes
  (`.test/.schema/.repository/.client/.mapper` in TS; `test_/_schema/_repository/_client/_mapper` in Python);
  ADRs `NNNN-PascalCaseTitle.md`.
- **Test locations:** unit/feature tests beside their code (`features/<f>/tests/`); cross-app/operational
  tests in the repo-root `tests/`; `tests/TESTING.md` is the strategy index.
- **Documentation requirements:** every feature has a block in its app `FEATURES.md`; every shared UI
  component a block in `packages/ui/.../COMPONENTS.md`; ADRs for durable decisions; docs ship in the same
  change as the code.
- **How relationships are documented:** each `FEATURES.md` block lists the feature's public exports, who may
  import it, contracts it publishes, external systems it calls, tables it owns, and shared components it uses
  — making the dependency graph readable from the docs.
- **Visual identification in the tree:** one folder per feature under `features/`, named for the outcome;
  one public entrypoint (`__init__.py`/`index.ts`) per feature; consistent sub-layer folder names so a
  feature is recognizable at a glance; shared UI isolated in `packages/ui`.

*(These would be applied to `.Claude/CLAUDE.md` only after you approve — not done in this read-only pass.)*

### C.3 Reality check (important, honest scoping)
Your brief assumes a large restructuring is needed. **It largely is not.** The backend is already a clean,
compliant feature-sliced architecture. The genuine restructuring work (§D) is **modest**: enforce feature
public surfaces, remove empty placeholder dirs, relocate `hashing.py`, fix the version mismatch, and build out
`apps/web`'s structure (which happens naturally in Phase 4). Do **not** rewrite working, well-structured code.

---

## D. Codebase Restructuring (audit → map → migrate → verify)

### D.1 Audit — current → correct location
| Current | Verdict | Action |
|---|---|---|
| `app/features/{confluence_sync,ingestion,retrieval,evaluation}/` | ✅ Correct feature slices | None |
| feature `application/domain/infrastructure/schemas/server/tests` sub-layers | ✅ Correct | None |
| `app/platform/{clients,config,db,jobs,logging}` | ✅ Correct shared kernel | None |
| `app/platform/hashing.py` (loose file) | ⚠️ Misplaced | Move into a named folder (e.g. `platform/hashing/`) or `shared/` |
| Feature deep-imports (no public surface) | ⚠️ Boundary debt | Add `__init__.py` public exports; update importers |
| `features/confluence_sync/domain/` (empty), `features/ingestion/schemas/` (empty) | ⚠️ Placeholder dirs | Delete until needed |
| `docs/architecture/`, `docs/runbooks/` (empty) | ⚠️ Empty | Fill (runbooks in Phase 5) or leave un-tracked |
| `main.py` 0.2.0 vs `pyproject` 0.1.0 | ⚠️ Mismatch | Pick one version, align |
| `apps/web/src/{app,features/chat}` (no `components/`,`shared/`,`platform/`) | ⚠️ Incomplete vs 5-folder rule | Build out during Phase 4 per the resolved standard |
| `packages/{contracts,design-tokens}` | ✅ Present | Populate `contracts` with the chat OpenAPI in Phase 4 |

### D.2 Duplicated / misplaced logic
- **No duplicated business rules found.** Domain concepts are owned single-source per feature.
- The only misplacement is the loose `hashing.py` primitive (above).

### D.3 Migration plan (safe, behavior-preserving — execute only after §C decision + your approval)
1. Resolve the standard (C.1) and write **ADR-0003**.
2. Delete empty placeholder dirs; strip stale `__pycache__`/`.pytest_cache`.
3. Introduce feature public surfaces (`__init__.py` exports), one feature at a time; update importers; run
   tests after each feature (green-to-green).
4. Relocate `hashing.py`; update imports.
5. Align the package version.
6. Update `FEATURES.md` blocks to list public exports + allowed importers (relationship docs).
7. (Frontend structure is built in Phase 4, not pre-emptively.)

### D.4 Verification after restructuring
- `ruff check app` clean, `pyright` clean, **`pytest` back to green** (after fixing bug #1 + debt #2),
  `python -c "import app.main"` OK, and the eval still beats baseline. No behavior change permitted.

---

## E. Remaining Implementation Phases

### Phase 4 — RAG agent & basic chatbot
- **Objective:** Typed orchestration agent + Next.js chat UI; streaming, grounded, cited answers.
- **Dependencies:** Phase 3 complete (✅); live Confluence + first real ingest done; §C/§D restructuring done.
- **Env:** `ANSWER_MODEL`, `ROUTING_MODEL` (live), `RERANKER_PROVIDER=cohere` + `RERANKER_API_KEY` (staged),
  `EVIDENCE_TOKEN_BUDGET`, `PROVIDER_TIMEOUT_SECONDS`; **new frontend** `apps/web/.env.local`
  (`NEXT_PUBLIC_API_BASE_URL`, auth vars).
- **Services:** automation (agent + chat HTTP/SSE endpoint), Postgres/pgvector, Anthropic, Cohere, Confluence.
- **Tasks:** auth/scope → conversation state → ambiguity/clarify → query rewrite → routing → hybrid retrieval
  → RRF → **cross-encoder rerank** (wire the staged Cohere/local path) → parent-context expansion → evidence
  check → one corrective-retrieval cycle → grounded generation → citation validation → streaming; **real ACL
  storage** (replace fixture-backed policy layer); `apps/web` chat UI (streaming, history, citation cards, dev
  trace panel); replace the `/api/chat` **501 stub** + validate inbound `ChatRequest`; publish the chat
  contract in `packages/contracts` (OpenAPI source of truth).
- **Testing:** agent step units; SSE parsing / partial + aborted streams; citation rendering; ACL enforcement
  (no cross-scope leak on real storage); grounding/no-hallucination checks; endpoint security per
  `securing-http-and-llm-endpoints` (it's an HTTP + LLM surface).
- **Completion criteria:** a user asks a question in the UI and gets a streamed, grounded, correctly-cited
  answer scoped to their permissions, over **real** embeddings and **real** Confluence content.
- **Deliverables:** `rag_agent` feature; chat UI; live `/api/chat`; ACL storage + migration; chat OpenAPI +
  generated types; tests; updated `FEATURES.md`.

### Phase 5 — Optimization & proof
- **Objective:** Prove accuracy and hit latency/cost targets; harden.
- **Dependencies:** Phase 4 working end-to-end.
- **Env:** optional hosted-rerank already covered; possible cache (Redis **only if** a real cache/queue/lock
  need is confirmed — proportionality gate); no new secrets by default.
- **Services:** eval harness at scale; optional cache; observability.
- **Tasks:** embedding/chunking/contextualization config sweeps; measure **reranking lift**; tune
  accuracy-before-latency; **prompt-injection + permission red-team tests**; full E2E; measured latency
  (targets from the plan: TTFT p50 < 1.5s / p95 < 2.5s, e2e p95 < 10s, retrieval p95 < 1.5s) and cost;
  caching + parallelization + safe fallbacks; **deploy/rollback runbooks** (fill `docs/runbooks/`).
- **Testing:** eval sweeps with recorded deltas; injection suite; latency benchmarks vs targets; E2E.
- **Completion criteria:** documented accuracy lift, targets met with evidence, injection/permission tests
  pass, runbooks exist.
- **Deliverables:** eval reports, security tests, latency/cost report, caching layer, runbooks.

### Phase 6 (PROPOSED — not in the original 5-phase plan)
> The plan defines exactly five phases. If you want a Phase 6, the natural scope is **production hardening &
> operations**: managed deploy (Supabase + host), secrets manager + key rotation, CI/CD (ruff/pyright/pytest +
> migrations gate), monitoring/alerting/tracing, backup & disaster-recovery for the versioned store, cost
> dashboards, and a formal service-account/permissions review. Flagged as proposed — confirm before planning.

---

## F. Prioritized Execution Checklist

Owner tags: **[YOU]** you must do · **[AGENT]** the coding agent does · **[BLOCKED]** waiting on info/credential.

### 1. Credentials & environment
- [ ] **[YOU]** Create Confluence **service account**, assign a **Confluence seat**, grant read on target spaces. *(BLOCKED: needs org-admin rights)*
- [ ] **[YOU]** Generate a **classic API token** as that account; send token + email.
- [ ] **[YOU]** Choose `CONFLUENCE_SPACES`.
- [ ] **[YOU]** (optional) Invent `CONFLUENCE_WEBHOOK_SECRET` if using live webhooks.
- [ ] **[YOU]** Decide Supabase now or later; if now, send the session-pooler `DATABASE_URL` + DB password.
- [ ] **[AGENT]** Fix bug #1 (empty the stray `CONFLUENCE_WEBHOOK_SECRET`); fetch `CONFLUENCE_SERVICE_ACCOUNT_ID`; re-run live tests. *(BLOCKED on token)*
- [ ] **[YOU]** Rotate the four keys pasted into chat once wired.

### 2. `.claude` architecture updates
- [ ] **[YOU]** Decide the C.1 standard (5-folder vs feature-shape reconciliation).
- [ ] **[AGENT]** Apply §C.2 additions to `.Claude/CLAUDE.md`; write **ADR-0003**.

### 3. Feature & component architecture design
- [ ] **[AGENT]** Define feature/component definitions, boundaries, naming, test/doc rules per the resolved standard (frontend gets the full 5-folder shape).

### 4. Current-code audit
- [x] **[AGENT]** Done in this handover (§D.1–D.2).

### 5. Codebase restructuring
- [ ] **[AGENT]** Execute §D.3 (public surfaces, remove placeholder dirs, relocate `hashing.py`, version align, update `FEATURES.md`) — green-to-green.

### 6. Build & regression testing
- [ ] **[AGENT]** Fix bug #1 + debt #2 (hermetic test settings); restore **99 green**; `ruff`/`pyright` clean; eval still beats baseline.
- [ ] **[YOU/AGENT]** **First real ingest** of 1–2 live pages; verify chunks/embeddings/citations/retrieval. *(BLOCKED on Confluence)*

### 7. Phase 4 — RAG agent & chat UI (per §E)
### 8. Phase 5 — Optimization & proof (per §E)
### 9. Phase 6 — Production hardening (proposed; confirm scope first)

**Do not start Phase 4 until items 2–6 are complete and verified.**

---

## G. Preserved Engineering Context (folded in from the two deleted handovers)

Kept because it prevents re-breaking solved problems. Pure session narrative was not preserved.

### G.1 Phase-2 engineering decisions (rationale — do not undo without reason)
- **D1 — `Document.page_id` FK is `DEFERRABLE INITIALLY DEFERRED`.** `page_source ⇄ document_version ⇄
  document` form an insert-order cycle; the registry row is written last in `stage_and_activate`, so a
  non-deferrable FK violates on **every first index**. Was latent because Phase 2 had never run. Flows into
  migration `0001` via `create_all`. **Do not revert to a plain FK.**
- **D2 — Finish + verify a phase before stacking the next.** Phase 2's sync core existed but had never run a
  job end-to-end; verifying it first surfaced two real bugs. Apply the same rule before Phase 4.
- **D3 — `FixtureConfluenceGateway` lives in `app/` (not `tests/`) with a LAZY loader import.** `main.py`'s
  offline path needs it, but the fixture corpus is a test artifact not shipped in the wheel; a top-level
  `import tests…` would break `import app.main` in production. It falls back to the base page file when a
  per-version snapshot is absent (only page 1001 has snapshots). **Keep the import lazy.**
- **D4 — Test-DB harness redirects the whole app engine at `omniboost_rag_test`** (env `DATABASE_URL` +
  `lru_cache` clear), scoped to `confluence_sync/tests`, autouse-truncate per test. The worker uses its own
  `session_scope`, so injecting sessions is not enough. Keeps the DB-free eval tests unaffected.
- **D5 — Worker uses 3 separate transactions:** claim (commit) → handle+complete (one tx) → fail (own tx). A
  shared claim+handler tx would roll back the attempts/lease increment on handler error → infinite retry with
  no backoff. Safe because handlers are idempotent + version-guarded. **Preserve the 3-tx split.**

### G.2 Known operational gotcha — stale dev DB
The **dev** database `omniboost_rag` (not the test DB) may still carry the **old non-deferrable FK** from
before D1; a first real index would fail there until rebuilt. The test DB is auto-rebuilt each pytest run, so
this is invisible in tests. **Before the first real ingest**, rebuild the dev DB:
`make down && make up && make migrate` (or `docker compose -f infra/foundation/docker-compose.yml down -v && up -d` then `alembic upgrade head`).
Status unconfirmed by the newer docs — verify before trusting a live index.

### G.3 Rejected paths (do not redo)
- Extending Mewsy_v2 (Node/Express flat-markdown) — can't meet pgvector/hybrid/event-sync.
- Non-deferrable `document.page_id` FK — breaks first index (see D1).
- Requiring a per-version snapshot for every fixture page — only 1001 has them; fall back to base file (D3).
- Postgres on `:5433` — port taken by `guided-setup-pg`; use **`:5434`** (our `omniboost_rag_pg`).
- Refactoring feature `__init__.py` to public-surface-only imports **as a big-bang** — do it incrementally
  (this is debt #3 / §D3, not a rejected goal).

### G.4 Run commands (reference)
```
pg:      docker compose -f infra/foundation/docker-compose.yml up -d      # omniboost_rag_pg, :5434
migrate: cd apps/automation && source .venv/bin/activate && alembic upgrade head
test:    cd apps/automation && source .venv/bin/activate && pytest        # DB tests need pg on :5434
lint:    ruff check app
eval:    python -m app.features.evaluation.run_baseline                   # or `make eval`
serve:   uvicorn app.main:app                                            # set enable_background_jobs=true for scheduler+worker
stack:   Python 3.12 (uv venv at apps/automation/.venv) · Node 24 / pnpm 10 · Postgres 16 + pgvector ≥0.8
ports:   :5434 = ours (use) · :5433 = guided-setup-pg (avoid)
```

### G.5 Exact Phase-3 re-verification checklist (from a clean context, before trusting it live)
1. Re-run the gates: `ruff check app && pytest -q && python -c "import app.main"` (expect 99 green **after**
   the `CONFLUENCE_WEBHOOK_SECRET` bug #1 fix).
2. Re-run the eval and **eyeball the rankings** (not just pass/fail): the right page ranks first per query;
   no restricted page appears for an unauthorized scope.
3. Independent **spec-vs-impl + security review** of the diff, focusing on: the atomic version swap +
   re-embed release gate (data-loss / mixed-version risk); the **two LLM-CALL surfaces** (OpenAI embeddings +
   Anthropic contextualization) against the `security_baseline` in `app/features/FEATURES.md`; permission
   filtering (policy-layer today — real ACL storage is Phase 4).
4. **First real ingest is the real test:** once the Confluence service account is live, index 1–2 real pages
   and check chunks, embeddings, citations, and retrieval sanity. Then re-run the eval against **real OpenAI
   embeddings** (Phase 3 was proven on the Fake provider + keyword path only).
