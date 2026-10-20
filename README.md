# Omniboost RAG

An accuracy-first, Confluence-native RAG chatbot. Confluence is the single source of
truth: pages are synced, chunked, embedded, and retrieved with hybrid (vector + full-text)
search, then answered with grounded citations. Freshness is kept up to date by inbound
Confluence webhooks plus scheduled reconciliation.

## Layout

This repository is an **Application Platform** monorepo (pnpm + Turbo workspace).

```text
backend/          Python 3.12 + FastAPI. Confluence sync, ingestion, retrieval, the RAG runtime, eval.
frontend/         Next.js 15 + React 19 + Tailwind. The chat widget, the embed frame and loader,
                  and the proxy that forwards chat to the backend.
knowledge-base/   The data layer: database schema, Alembic migrations, JSON config
                  (product catalog, platforms), seeds, and the local pgvector docker-compose.
packages/
  contracts/      OpenAPI source of truth + generated/hand-written types (chat + Confluence events).
  design-tokens/  Semantic design tokens and the Tailwind theme extension.
services/
  obi-confluence-sync/  Forge app that forwards Confluence page and label events to the backend.
docs/
  adr/            Architecture Decision Records (named, not numbered; see docs/adr/README.md).
```

TypeScript owns everything a human looks at (and the proxy that serves it). Python owns the
backend: sync, pipelines, model orchestration, and evaluation. The two languages never
share code — they agree through `packages/contracts`.

Both apps run on Railway: the frontend at `https://obi-web-production.up.railway.app`
(deploy with `scripts/deploy-frontend.sh`) and the backend at
`https://obi-backend-production.up.railway.app` (deploy with `railway up --service obi-backend`
from the repo root). A git push does not deploy. See `docs/runbooks/`.

## Prerequisites

- **Docker** (for Postgres + pgvector via docker-compose)
- **uv** (Python 3.12 environment + dependency management for `backend`)
- **pnpm** (JavaScript workspace package manager)
- **Node.js** LTS (v20+; developed on v24)

## Quickstart

Copy the example environment file and fill in secrets:

```bash
cp .env.example .env
```

Start Postgres (pgvector on host port 5434):

```bash
docker compose -f knowledge-base/local/docker-compose.yml up -d
```

Set up the Python backend:

```bash
cd backend && uv venv --python 3.12 && uv pip install -e ".[dev]"
```

Run database migrations:

```bash
uv run alembic -c ../knowledge-base/migrations/alembic.ini upgrade head   # or `make migrate` from the repo root
```

Run the backend test suite:

```bash
uv run pytest
```

Run the retrieval evaluation baseline (from the repo root):

```bash
make eval
```

Run the web app. Next.js does not read the repo-root `.env`, so the chat proxy needs its own
copy (same `CHAT_API_KEY` value as the root `.env`, plus the backend's base URL in `AUTOMATION_API_BASE_URL`):

```bash
cp frontend/.env.example frontend/.env.local  # then fill in CHAT_API_KEY to match the root .env
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
design-vs-code gap.
