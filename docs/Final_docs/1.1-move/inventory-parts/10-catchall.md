# 10 · Catch-all sweep — references other targeted greps might miss

READ-ONLY inventory for the 1.1 folder move (`apps/web → frontend/`, `apps/automation → backend/`, db+migrations+config+seed+local → `knowledge-base/`).

Sweep command (from repo root):

```
grep -rn "apps/web\|apps/automation\|infra/foundation\|config/knowledge_scopes\|platform.db\|infra/" . \
  --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.next
# plus a broad pass for "apps/" and "foundation"
```

## What the bulk of the hits are (already owned, not surprises)

- **`apps/automation/app/**/*.py` and its tests** — the overwhelming majority are internal Python imports that match `platform.db` / `config/knowledge_scopes` (e.g. `from app.platform.db import ...`, `app.platform.config.knowledge_scopes`). The `app/` package is **kept as-is** under `backend/`, so these imports stay valid unchanged. Owned by the code-move / python-config buckets (02, 07, 09).
- **`apps/web/src/**`** (chat-widget, route.ts, i18n, knowledge-scopes.ts, platforms.ts, tailwind.config.ts, platform READMEs) — JS workspace, folder rename only; package name `web` is unchanged. Owned by **05-js-workspace**.
- **`packages/**`** (`contracts/src/index.ts`, `contracts/src/token-claims.json`, `contracts/src/openapi/chat.yaml`, `design-tokens/src/tailwind-theme.ts`) — comment/description strings that name `apps/web` / `apps/automation`. `packages/*` **stays put**; owned by **05-js-workspace** (its scope explicitly names these files). Will still want a comment refresh when `apps/*` folders rename.
- **Excluded-by-instruction buckets** present in the sweep: `Makefile`, `.github/workflows/ci.yml`, `pyproject.toml`, `pnpm-workspace.yaml`, `pnpm-lock.yaml`, `package.json`, `turbo.json`, `alembic*`, `.claude/**`, `CLAUDE.md`, `settings.py`, `.env*`. Owned by parts 02–09.
- **Under `docs/` and `docs/Final_docs/`** — hundreds of hits (audit docs, ledger, ADRs, `_archive/`, embedding docs, this inventory's sibling parts). **These two trees are excluded from the proof grep**, so their path strings do NOT block the proof. Not authoritative / mostly historical; may still want fixing where they document the live layout (e.g. `docs/OBI-RAG-SYSTEM-A-Z.md`, `docs/runbooks/*`, `docs/adr/0007`, `docs/adr/0010`). Flagged here for awareness only; not counted as leftovers.

---

## LEFTOVERS not owned by another bucket

These are the surprises — real files, outside `docs/`/`docs/Final_docs/`, that no targeted grep (02–09) claims, and that will go stale on the move. Full `path:line: text`:

### README.md (repo root) — describes the live tree + setup commands
```
README.md:13:apps/
README.md:19:infra/
README.md:20:  foundation/     Shared infra (Postgres + pgvector via docker-compose).
README.md:33:- **uv** (Python 3.12 environment + dependency management for `apps/automation`)
README.md:48:docker compose -f infra/foundation/docker-compose.yml up -d
README.md:54:cd apps/automation && uv venv --python 3.12 && uv pip install -e ".[dev]"
README.md:79:cp apps/web/.env.example apps/web/.env.local  # then fill in CHAT_API_KEY to match the root .env
```

### tests/TESTING.md — documents where tests live per app
```
tests/TESTING.md:6:  - Python (`apps/automation`): tests sit inside each feature at
tests/TESTING.md:7:    `apps/automation/app/features/<feature>/tests/` (or the app's existing
tests/TESTING.md:9:  - TypeScript (`apps/web`): feature-scoped tests sit in
tests/TESTING.md:10:    `apps/web/src/features/<feature>/tests/`. The web test runner is wired with
tests/TESTING.md:13:  and operational tests** — anything that spans `apps/web` and `apps/automation`
tests/TESTING.md:30:make test                     # == cd apps/automation && uv run pytest
```

### .gitignore — ignore paths keyed to the widget folder
```
.gitignore:43:apps/web/public/obi.js
.gitignore:46:apps/web/test-results/
.gitignore:47:apps/web/playwright-report/
.gitignore:48:apps/web/blob-report/
```

### config/platforms.json — `_readme` names a sibling config file by path
```
config/platforms.json:2:  "_readme": "... 'integrations' maps that key to the live obi-*-test knowledge scopes from config/knowledge_scopes.json. ..."
```
(The `config/` tree itself moves to `knowledge-base/config/`; this self-reference to `config/knowledge_scopes.json` inside the JSON string goes stale unless updated.)

### Also present but NOT counted (target files of the move, not stale references)
- `infra/foundation/docker-compose.yml` and `infra/foundation/init/01-roles.sql` exist and are the *destinations* named by README/.env; their own contents held **no** `apps/`/`infra/` path strings. They are the thing being moved, not a dangling pointer — likely owned by an infra/local-compose bucket (missing part 01/06).

**No shell scripts (`.sh`), root-level `.sql`, `.toml`, or `.yaml` (other than the already-owned `pnpm-*.yaml` / `pyproject.toml`) reference the moved paths.** The only `.sh` on disk is inside `.venv` (excluded).
