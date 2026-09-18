# Omniboost RAG

An accuracy-first, Confluence-native RAG chatbot. Confluence is the single source of
truth: pages are synced, chunked, embedded, and retrieved with hybrid (vector + full-text)
search, then answered with grounded citations. Freshness is kept up to date by inbound
Confluence webhooks plus scheduled reconciliation.

## Layout

This repository is an **Application Platform** monorepo (pnpm + Turbo workspace).

```text
apps/
  web/            Next.js 15 + React 19 + Tailwind. Chat UI; proxies chat SSE to the API.
  automation/     Python 3.12 + FastAPI. Confluence sync, ingestion, retrieval, RAG runtime, eval.
packages/
  contracts/      OpenAPI source of truth + generated/hand-written types (chat + Confluence events).
  design-tokens/  Semantic design tokens and the Tailwind theme extension.
infra/
  foundation/     Shared infra (Postgres + pgvector via docker-compose).
docs/
  adr/            Architecture Decision Records.
tests/            Cross-application and operational tests (see tests/TESTING.md).
```

TypeScript owns everything a human looks at (and the proxy that serves it). Python owns the
automation: sync, pipelines, model orchestration, and evaluation. The two languages never
share code — they agree through `packages/contracts`.

## Prerequisites

- **Docker** (for Postgres + pgvector via docker-compose)
- **uv** (Python 3.12 environment + dependency management for `apps/automation`)
- **pnpm** (JavaScript workspace package manager)
- **Node.js** LTS (v20+; developed on v24)

## Quickstart

Copy the example environment file and fill in secrets:

```bash
cp .env.example .env
```

Start Postgres (pgvector on host port 5434):

```bash
docker compose -f infra/foundation/docker-compose.yml up -d
```

Set up the Python automation app:

```bash
cd apps/automation && uv venv --python 3.12 && uv pip install -e ".[dev]"
```

Run database migrations:

```bash
uv run alembic upgrade head
```

Run the automation test suite:

```bash
uv run pytest
```

Run the retrieval evaluation baseline (from the repo root):

```bash
make eval
```

Run the web app. Next.js does not read the repo-root `.env`, so the chat proxy needs its own
copy (same `CHAT_API_KEY` value as the root `.env`, plus the automation API's base URL):

```bash
cp apps/web/.env.example apps/web/.env.local  # then fill in CHAT_API_KEY to match the root .env
pnpm install && pnpm --filter web dev
```

Common tasks are also wired in the root `Makefile` (`make up`, `make down`, `make migrate`,
`make test`, `make eval`, `make web-dev`, `make fmt`).

## Environment variables

All configuration lives in `.env` (never committed). See `.env.example` for the full,
documented list: Confluence Cloud credentials and webhook secret, model + embedding +
reranker settings, `DATABASE_URL`, retrieval budgets, and reconciliation schedules.

## Phase status

**`docs/Final_docs/ledger.md` is the single source of truth for current progress** — one line
per finished substep with commit, tests, and deviations. `docs/Final_docs/obi-action-plan.html`
is the work list; `docs/plan/decisions.md` and `docs/plan/delta.md` hold open decisions and the
design-vs-code gap. The pre-Phase-0 `docs/rag/PLAN.md` this section used to point to is archived
under `docs/_archive/rag-legacy-pre-phase0/` and is no longer authoritative.
