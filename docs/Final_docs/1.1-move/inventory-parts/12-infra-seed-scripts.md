# 12 · infra / seed / scripts move inventory

Three moves under test:
- `infra/foundation/` → `knowledge-base/local/`
- `apps/automation/scripts/seed_curated_knowledge.py` → `knowledge-base/seed/`
- `config/knowledge_scopes.json` → `knowledge-base/config/`

## (A) `infra/foundation/docker-compose.yml` + `infra/foundation/init/01-roles.sql`

Contents under `infra/foundation/`: `docker-compose.yml`, `init/01-roles.sql`. Nothing else.

Path references in the compose file:
- `image: pgvector/pgvector:pg16@sha256:1d53...` — pinned by digest, not a path. Safe.
- Volume `rag_pg_data:/var/lib/postgresql/data` — named docker volume, no host path. Safe.
- Volume mount `./init:/docker-entrypoint-initdb.d:ro` — **relative to the compose file's own location**. `init/` moves inside `foundation/` alongside the compose file, so this travels WITH the file. Safe.
- No `build:` key anywhere. No build context, no reference to app source, no absolute or repo-relative path.

`01-roles.sql` is plain SQL (creates `rag_reader` role); no path references at all.

**Verdict:** the compose file has NO build context and NO repo-relative/absolute path. Every path is relative-to-compose-file (`./init`) and moves together. Safe to move as a self-contained unit.

## (B) `seed_curated_knowledge.py`

Purely arg-driven. Reads no adjacent JSON/CSV/SQL fixture. Input is CLI args (`--title`, `--body`, `--tags`, `--id`, `--deactivate`). Its only external deps are code imports (`app.platform.db.engine`, `app.platform.db.models`) — not data files. Nothing extra needs to move with it.

## (C) root `config/` after moving `knowledge_scopes.json`

`config/` currently holds: `knowledge_scopes.json`, `obi_identity.md`, `platforms.json`, `platforms.local.json`.

Only `knowledge_scopes.json` moves. Root `config/` does NOT empty out — three files remain: `obi_identity.md`, `platforms.json`, `platforms.local.json`.

---

## Answers

1. **Compose:** No — no build context, no repo-relative/absolute path. The only relative path (`./init`) is compose-file-relative and moves with the file. Safe.
2. **Seed script data file:** None. Purely arg-driven CLI; only code imports, no fixture file.
3. **Root `config/` after move:** Not empty — `obi_identity.md`, `platforms.json`, `platforms.local.json` remain.
