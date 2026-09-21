# Testing Strategy

## Where tests live

- **Unit and feature tests live beside the code they test.**
  - Python (`backend`): tests sit inside each feature at
    `backend/app/features/<feature>/tests/` (or the app's existing
    `tests/` convention), run with `pytest`.
  - TypeScript (`frontend`): feature-scoped tests sit in
    `frontend/src/features/<feature>/tests/`. The web test runner is wired with
    the Phase 4 chat UI; there are no web tests yet.
- **This `tests/` directory holds cross-application, integration, end-to-end,
  and operational tests** — anything that spans `frontend` and `backend`
  or exercises real infrastructure. These arrive later (see phase status in the
  root `README.md`); the directory is scaffolded now.

## What to cover first

- Automation: Confluence sync idempotency, ingestion/chunking correctness,
  retrieval ranking, and the RAG runtime's grounding + citation behavior.
- Web (Phase 4): SSE stream parsing, partial/aborted streams, citation
  rendering.
- Cross-app (later): the web → automation chat proxy end to end against a
  running API and Postgres.

## How to run

```bash
# Automation unit/feature tests
make test                     # == cd backend && uv run pytest

# Retrieval evaluation baseline
make eval

# Web build (type/compile check for the shell)
pnpm --filter web build
```

Postgres must be running for integration tests: `make up`.
