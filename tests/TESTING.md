# Testing Strategy

## Where tests live

- **Unit and feature tests live beside the code they test.**
  - Python (`apps/automation`): tests sit inside each feature at
    `apps/automation/app/features/<feature>/tests/` (or the app's existing
    `tests/` convention), run with `pytest`.
  - TypeScript (`apps/web`): feature-scoped tests sit in
    `apps/web/src/features/<feature>/tests/`. The web test runner is wired with
    the Phase 4 chat UI; there are no web tests yet.
- **This `tests/` directory holds cross-application, integration, end-to-end,
  and operational tests** — anything that spans `apps/web` and `apps/automation`
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
make test                     # == cd apps/automation && uv run pytest

# Retrieval evaluation baseline
make eval

# Web build (type/compile check for the shell)
pnpm --filter web build
```

Postgres must be running for integration tests: `make up`.
