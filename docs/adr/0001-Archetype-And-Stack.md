# 0001 — Repository Archetype and Stack

Status: Accepted
Date: 2026-07-28
Governs: entire repository

## Decision

Build a new **Application Platform** (per the global Architecture Standard §4B):

- `apps/web` — Next.js + React + TypeScript + Tailwind + semantic design tokens. Renders the
  streaming chat UI and proxies chat SSE to the automation API (thin route handler).
- `apps/automation` — Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic. Owns
  Confluence synchronization, ingestion/indexing, hybrid retrieval, the RAG runtime agent, and
  evaluations. Tooling: uv, Ruff, Pyright, pytest.
- `packages/contracts` — OpenAPI source of truth for the chat API and the Confluence event
  envelope; generated TypeScript + Pydantic types.
- Data: PostgreSQL 16 + pgvector + Postgres full-text search (tsvector).

## Reason

The task requires an event-driven ingestion pipeline, document processing, model orchestration,
and a versioned vector store. Per the global standard's language split, that automation surface
is Python; the user-facing chat interface and its serving proxy are TypeScript. A single
`apps/automation` FastAPI service is allowed to expose the chat HTTP endpoint even though it is
"automation," so no separate `apps/api` is created.

## Alternatives considered

- **Extend the Mewsy_v2 prototype (Node/Express, flat markdown).** Rejected: its non-vector
  architecture cannot meet pgvector/hybrid-retrieval/event-sync requirements without wholesale
  replacement, and it conflicts with the language split. Kept only as prior-art reference.
- **Single Python service with a server-rendered UI.** Rejected: the task requires a responsive
  streaming chat interface; Next.js is the standard for that surface.

## Paths governed

`apps/**`, `packages/**`, `infra/**`, repository root config.
