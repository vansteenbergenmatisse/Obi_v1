# Obi · project instructions

Obi is an accuracy-first RAG chatbot over Omniboost's Confluence pages. It answers with citations or refuses with a reason. Two workflows: **ingestion** (a published page becomes chunks with vectors) and **retrieval** (a question becomes a cited answer). One Postgres on Supabase with pgvector is both the relational store and the vector store. Seven to nine seconds per answer is accepted; a wrong answer is not.

## Where the truth lives

- The design page *Obi, part by part* (HTML) in `docs/design/` is the source of truth for what every stage must do. Every box on it is a panel with a `today` line, a target, and tests. When code, plan or this file disagree with it, the design page wins and the other one gets fixed.
- The action plan (HTML) in `docs/design/` is the only work list. Work on exactly one substep at a time.
- `docs/plan/` holds the decisions the owner made, the delta between code and design, and the status ledger. The ledger is the honest record of progress: one entry per finished substep with commit, test count and deviations.
- `docs/adr/` holds decisions of record. Changing one needs a new ADR.
- `docs/future-ideas.md` holds deferred ideas: what each is, why it is deferred, where in this plan it would land, and the date added. Not scheduled work.
- Everything else under `docs/` is archived in Phase 0 and is not authoritative until reviewed.

## Commands

Run backend commands from the backend folder with `uv run`. Package managers do not mix: `uv` for Python, `pnpm` for the JS workspace.

```
make up          # local Postgres with pgvector on :5434
make migrate     # alembic upgrade head
make test        # backend suite: unit and database tests, hermetic settings, test database
make eval        # gold-set runner, per stage
make boundaries  # architecture gate, must exit 0
make check       # boundaries + tests, the enforced gate before any commit
make web-dev     # Next.js dev server
uv run ruff check . && uv run ruff format --check . && uv run pyright
```

Secrets come from the root `.env` (gitignored). Tests never read it. `/obi-verify` runs every level and prints one table.

## Where things go

Backend (Python, FastAPI):
- The entrypoint module is wiring only: settings, engines, services, routers, scheduler. No business rules.
- `features/confluence_sync/` owns ingestion stages 1 and 2: webhook, event ledger, job queue and worker, sweeps, change classification, labels to scope state.
- `features/ingestion/` owns stages 3 and 4: normalize, chunk, contextualize, attachments, embed, version, swap, garbage collection, rollback.
- `features/retrieval/` owns retrieval stages 2 to 4: hybrid search, fusion, page permissions, rerank wiring, trace writes.
- `features/rag_agent/` owns stages 1 and 5: the chat endpoint, token and key checks, limits, small talk, rewrite, refusal, generation, citations, the support check, prompts, curated knowledge.
- `features/evaluation/` owns the eval runner, metrics and datasets.
- `platform/` owns technical capabilities: database models, roles and policies, API clients, settings, the job queue, logging.
- `shared/` owns small cross-feature primitives with no clearer owner (hashing, rate limiter, TTL cache). A primitive goes here, not in `platform/`.
- Every prompt lives in the rag_agent domain layer. No prompt text anywhere else.
- Migrations are numbered, each has a downgrade, and every schema change on the design page lives in one migration.
- Operator tools (Supabase setup and isolation check, seeds, sweeps, backfill and readiness gate, key rotation) live in `scripts/`.

Frontend (Next.js): the widget UI, the proxy route that adds the host key, the embed frame, the loader script, i18n, the generated scope list. UI components exist only here.

Config is data: the tag map and the platform list are JSON under `config/`. Nothing else may define a tag or a platform.

Tests: unit tests with fakes and database tests next to the feature they cover; browser tests in the frontend; eval datasets in `features/evaluation/`. Names: `test_<stage>_<behavior>`. Every regression test names the design panel it protects.

<!-- Phase 1 of the plan moves apps/web → frontend/, apps/automation → backend/, and db models + migrations + config + seeds + local compose → knowledge-base/. Same placement rules, new top folders. Rewrite this section then and delete this note. -->

After the Phase 1 move, the same rules hold under three top folders: `frontend/`, `backend/`, `knowledge-base/` (schema, migrations, config, seed, local). `backend` imports `knowledge-base/schema`; `knowledge-base` imports nothing from `backend`; `frontend` imports neither and reads config as JSON at build time.

## Boundaries (enforced by `make boundaries`)

Every feature and `platform/clients` expose one public root that re-exports what crosses its boundary. Four rules fail the build:

1. Code outside a feature imports it at its root, never deeper.
2. Code inside a feature may deep-import itself, but reaches other features at their root.
3. Code inside a feature never imports its own root (a half-built package raises at init).
4. `platform/` and `shared/` import no feature; `shared/` imports no `platform/`.

Exception: database models and enums are imported by full path, not through a facade (ADR-0003). When another module needs a symbol, export it from the feature root.

## Rules that never bend

1. Never disable row security on any Supabase table. Never run the 0009 downgrade on Supabase. Both expose the corpus through the public REST roles.
2. The request body never decides access. Scope, company, integration and identity come from the verified token. A body scope is checked for shape and membership only: unknown is a 400 before any search; a known value that disagrees with the token is ignored and logged.
3. One authorization context per request, built at the gate. Every database read (search, rerank text, curated lookup, parent expansion) sets both scope settings from it. No read runs under looser rules than the search.
4. A rebuild embeds the whole page. No vector is reused from an old version.
5. A page is in the index for one reason: it is published and carries a tag from the tag map. Losing the last tag deactivates it; `classified` deletes it. Folder roots decide nothing.
6. The exact chunk that matched is what the reranker scores and what expands to a parent. Never a stand-in from the same page.
7. Nothing is sent before every sentence cites a real source and every cited source backs its sentence. Refuse with a reason rather than guess.
8. At most two extra reads per question: the thin-results refetch and the weak-score fallback. Never a loop.
9. Non-English questions are translated to English before search; the checked English answer is translated back before the replay. Citations, markers and the trace stay English.
10. No secret in the repository, a log line, a trace row, a URL, a cookie or web storage. Never interpolate a secret into SQL. The user token lives in memory only.
11. No change without its test. No retrieval change without a before-and-after number on the held-out gold set. Migrations are reversible.
12. Never invent connection strings, keys, scaling or latency numbers. Ask, and record the blocker in the ledger.

## How work happens

- Take one substep from the action plan. Read it and the design panels it names. Run `/obi-change`. Stop when its test is green and the ledger entry is written.
- Failing test first, with `/obi-test-writer`. Tests are deterministic: fakes for Confluence, embeddings, the reranker and Claude; database tests roll back; no sleeps.
- Files you touch are brought clean under ruff and pyright. Files you did not touch are not reformatted. Whole-repo counts never rise above the recorded baseline (ADR-0003 D1).
- When a substep is done: flip the panel status and its `today` line on the design page, regenerate the brief from it, update the ingestion or retrieval phase docs, append the ledger entry.
- Anything marked "Decision needed" is built to the default in `docs/plan/` and named as such in the pull request.
- Stop after every substep. Hand back a short summary and ask for `/compact-ultra`. Do not start the next substep without a go-ahead.
- Before starting a substep, verify the previous one: security review with `securing-http-and-llm-endpoints` for anything touching an endpoint, an LLM call or outbound network; every acceptance line has an assertion; `make check` green; migrations reversible. A failure becomes the next ledger task and is fixed first.
- Blockers only the owner can clear (connection strings, keys, tokens, a platform's public key, a product decision) go into the ledger under "need from you". Ask before doing other work.
- Subagents: `obi-auditor` reads and reports, never edits; `obi-implementer` runs `/obi-change`; `obi-tester` runs tests and reports. They do not discover skills on their own; their definitions preload the ones they need.

## Test levels

| Level | Means | Runs with |
|---|---|---|
| unit | fakes, no network | `make test` |
| database | local pgvector Postgres, migrations to head, both roles, all policies, row security on, rolled back per test | `make test` |
| live | a script against staging or production (isolation check, live label check, freshness proof); output goes in the pull request | by hand |
| browser | Playwright against a stub host page | `pnpm test:e2e` |
| eval | the gold-set runner, per stage, before and after | `make eval` |

## Words with one meaning

- **Implemented**: deployed and tested on the live store. **Implemented, needs changing**: runs today, the target changes it. **Planned**: not in code. **Unverified**: coded, not applied or not proven live. **Decision needed**: blocked on the owner.
- **Priority 1**: the exact chunk from search to answer. **Priority 2**: the batched support check before send.
- **Parent** (about 1200 tokens) is what the answer model reads; **child** (about 400) is what search matches. **Knowledge scope**: a tag from the tag map. **Authorization context**: the one object built at the gate. **The note**: the signed JWT a platform hands the widget. **Locks 0 to 3**: the edge, source row security, scope row security, page permissions.