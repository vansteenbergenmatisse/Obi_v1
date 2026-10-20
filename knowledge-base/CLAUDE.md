# knowledge-base/ · ownership and shared contracts

Read the root `CLAUDE.md` first — it is authoritative for the whole repo. This file states only what
`knowledge-base/` owns and its coupling rules.

## What this folder owns

The data layer. Distributed as the package `obi-knowledge-base`, **imported as `schema`**. It imports
nothing from `backend/` or `frontend/` (ADR-features-import-only-through-public-root, the one-way rule; enforced by `make boundaries`).

- `schema/` — SQLAlchemy models, enums (mapped 1:1 to Postgres ENUMs), the writer/reader engines (`engine.py`), RLS/role helpers, and `settings.py` (`KbSettings`, reads the same `.env` as the backend). The embedding column switches to `halfvec` above 2000 dims.
- `migrations/` — a self-contained Alembic project (`alembic.ini`, `env.py`, `versions/0001…`). **Every schema change on the design page is one migration; every migration has a downgrade.** This is the only Alembic project in the repo.
- `config/` — the canonical JSON registries, edited by operators, read by both apps:
  - `knowledge_scopes.json` — the single allowlist of knowledge-scope tags.
  - `platforms.json` — the platform / JWT-issuer registry + integration→scope map (production values).
  - `platforms.local.json` — local-only test-host issuers (localhost; **rejected in a production env**).
- `seed/` — the curated-knowledge seed CLI. `local/` — the local pgvector docker-compose + `rag_reader` role SQL (dev only; not deployed).
- `tests/` — schema/migration/RLS tests, run from this folder's own venv.

## Contracts it shares with the other roots

- **The `schema` package is the backend's entire DB layer.** The backend imports `schema.engine`, `schema.models`, `schema.enums` by full path (ADR-features-import-only-through-public-root exception — models/enums are not facaded).
- **`config/*.json` are read at runtime by both the backend (boot) and the frontend (embed CSP, server-side).** Changing a scope tag or platform means editing these files — nothing else may define a tag or platform.
- It ships **with the backend** in the deploy image (siblings under one root), because the backend resolves both the import and the config paths relative to that layout.

## Rules that never bend (see root CLAUDE.md)

- Never disable row security on any Supabase table. **Never run the 0009 downgrade on Supabase.** Both expose the corpus through the public REST roles.
- A rebuild embeds the whole page; no vector is reused from an old version.

## Commands

Migrations run from `backend/` (which has `obi-knowledge-base` installed) pointing Alembic at this
project: `make migrate` → `alembic -c ../knowledge-base/migrations/alembic.ini upgrade head`. This
folder's own tests run via `cd knowledge-base && uv run pytest`.
