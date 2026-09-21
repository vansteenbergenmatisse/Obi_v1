# 1.1.1 move — inventory (the checklist)

Every file the move touches, grouped. Built by fan-out (12 read-only agents) + owner cross-check
**before** anything moved. Exact `path:line: text` hits live in `inventory-parts/NN-*.md`; this file is
the synthesized checklist for the rewrite (Step 5) and the record for the PR. The break-it result is
appended at the bottom after Step 8.

## Ground-truth corrections to the plan text (real paths differ from the design page)
- Backend Python package root is `apps/automation/app/` (kept as `backend/app/`). Imports are `app.platform.db.*` (147 statements, 80 distinct files), **not** `platform.db.*`.
- `scripts/`, `tools/`, `tests/` are inside `apps/automation/`, not repo root.
- Seed script is arg-driven; **no data file** moves with it.
- No Dockerfiles, no hosting config exist — those plan bullets are no-ops.
- Root `config/` does **not** empty out: `obi_identity.md`, `platforms.json`, `platforms.local.json` stay.

## The moves (git mv, in order) — Step 3
| # | from | to | notes |
|---|---|---|---|
| 1 | `apps/web` | `frontend` | widget; pnpm package name stays `web` |
| 2 | `apps/automation` | `backend` | keeps inner `app/` package |
| 3 | `backend/app/platform/db/` **module files** (`__init__,base,engine,enums,models,schema`) | `knowledge-base/schema/` | tests handled separately (see #3b) |
| 3b | `backend/app/platform/db/tests/` | `backend/tests/schema/` | **stays in the backend suite** (keeps conftest + collection + count); repoint imports. Deviation from a naive whole-dir move — see "db-tests decision" below |
| 4 | `backend/alembic/` | `knowledge-base/migrations/` | |
| 5 | `backend/alembic.ini` | `knowledge-base/migrations/alembic.ini` | |
| 6 | `config/knowledge_scopes.json` | `knowledge-base/config/knowledge_scopes.json` | only this file leaves `config/` |
| 7 | `backend/scripts/seed_curated_knowledge.py` | `knowledge-base/seed/` | the other 6 scripts stay in `backend/scripts/` |
| 8 | `infra/foundation/` (compose + `init/01-roles.sql`) | `knowledge-base/local/` | self-contained; no build context, safe |

Stay put: `packages/`, `docs/`, `docs/Final_docs/`, `.claude/`, `.github/`.

## KEY DEVIATION — db config decoupling (owner-approved: self-contained schema settings)
`db/` currently imports **backend** config, which would make knowledge-base depend on the backend (violates the 1.1.2 one-way rule). Owner chose **self-contained schema settings**. See `inventory-parts/11-backend-structure-audit.md`.
- `engine.py:12` `from app.platform.config import get_settings` → new `schema/settings.py` (`get_kb_settings`).
- `models.py:36` same import; `models.py:46` `EMB_DIM = get_settings().embedding_dim` → `get_kb_settings().embedding_dim`.
- New `knowledge-base/schema/settings.py`: pydantic `BaseSettings` (`KbSettings`) with fields `env`, `database_url`, `database_reader_url`, `embedding_dim` + `is_offline_env()`, **same `env_file=(".env","../../.env")`** so it reads identical env + .env values (no 1024-vs-3072 drift). Defaults copied from `app/platform/config/settings.py` (env `local`, url `...:5434/omniboost_rag`, reader `""`, dim `1024`).
- `alembic/env.py:8-12`: drop `from app.platform.config import get_settings`; get the URL from `schema.settings` (or `os.environ["DATABASE_URL"]`); import `Base`/`models` from `schema.*`. This is what lets migrations run without `app` on the path.
- This is a **logic change** beyond "rename-only"; recorded because the design's own architecture (knowledge-base imports nothing back; separate repos later) requires it, and the alembic relocation forces it. Behavior preserved: same settings sources, verified by the full suite + a new test that `import schema` pulls in zero `app.*` modules.

## Python import rewrites — Step 5 (see `inventory-parts/01-python-db-imports.md`)
147 statements across 80 files. `sed` per kind, then `ruff check backend` + `ruff check` on schema:
- `.models` ×45, `.engine` ×38, `.enums` ×24, `.base` ×5, `from app.platform.db import <sub>` ×35.
- `app.platform.db.models → schema.models`; `.engine → schema.engine`; `.enums → schema.enums`; `.base → schema.base`; `from app.platform.db import schema → from schema import schema`; package `app.platform.db → schema`.
- Inside the moved db modules, internal imports are **absolute** (`from app.platform.db.base import Base`) → become `from schema.base import Base` (not relative).
- Care items: 8 function-local imports (`sync_service.py:88`; `test_ingestion_pipeline.py:203,235,236,263,264,297`; `test_customer_isolation_backstop.py:45`); 4 docstring string-literals (prose only, leave or update text) in `test_s_reader_role_usage.py:17`, `test_vector_data_nearest.py:16`, `test_vector_data_keyword.py:10`, `test_s_reader_curated_fetch.py:10`.

## db-tests decision (Step 3b)
The 10 files in `db/tests/` import `app.platform.config` + `app.platform.db.*` and rely on `apps/automation/conftest.py`. They cannot sit in knowledge-base importing `app`. They move to `backend/tests/schema/` (still under backend's `testpaths=["app","tests"]`, still covered by the root conftest → collection + count preserved). Imports repointed: `app.platform.db.* → schema.*`; `app.platform.config get_settings/Settings → schema.settings` (matching the new engine/models source). A future substep may give knowledge-base its own test runner (future-ideas).

## alembic — Step 5 (see `inventory-parts/02-alembic.md`)
- `alembic.ini`: `script_location = .`; `prepend_sys_path` → `..` (so `knowledge-base/` is on the path → `import schema` resolves); keep `path_separator = os`; `sqlalchemy.url` stays absent (set in env.py).
- `env.py`: imports from `schema.*`; URL from `schema.settings`/env (no `app.*`).
- 4 version files import enums: `0001, 0002, 0009, 0010` — `from app.platform.db import schema` → `from schema import schema`.

## Makefile — Step 5 (see `inventory-parts/03-makefile.md`)
- Line 7 `AUTOMATION := apps/automation` → `backend`; line 8 `COMPOSE := infra/foundation/docker-compose.yml` → `knowledge-base/local/docker-compose.yml`; header comments lines 3-4.
- `migrate` + `test-db` alembic calls must point at the moved ini: add `-c knowledge-base/migrations/alembic.ini` (the agent's "no text change" was incomplete — with the ini gone from `backend/`, alembic won't find it). `01-roles.sql` mount travels with the compose file (in-container path unchanged).

## CI `.github/workflows/ci.yml` — Step 5 (see `inventory-parts/04-ci.md`)
- Lines 23 & 31: `cd apps/automation` → `cd backend`.
- Test-count **floor = 621** at line 34 (mirrored in step name line 29 + error line 35). No change in 1.1.1; **bump in 1.1.2** when new boundary tests are added.
- No compose path / working-directory / cache-key edits needed here.

## JS workspace — Step 5 (see `inventory-parts/05-js-workspace.md`)
- `pnpm-workspace.yaml` line 2: `"apps/web"` → `"frontend"`.
- `pnpm-lock.yaml`: **regenerate via `pnpm install`** (importer key), do not hand-edit (CI uses `--frozen-lockfile`).
- `frontend/src/features/embed/platforms.ts:29`: `../` depth 5→4, target stays root `config/platforms.json`.
- `frontend/src/features/chat/tests/knowledge-scopes.test.ts:18`: `../` depth 6→5 **and** target → `knowledge-base/config/knowledge_scopes.json`.
- Verified NOT needing edits: root `package.json`, `turbo.json`, `apps/web/package.json`, `tsconfig.json`, `next.config.ts`, `playwright.config.ts`, `vitest.config.ts`. (6 cosmetic comment-only `apps/web` mentions optional.)

## Settings / env code paths — Step 5 (see `inventory-parts/09-settings-env.md`) — CODE edits, not just strings
- `backend/app/platform/config/knowledge_scopes.py:17-19`: `parents[5] / "config" / "knowledge_scopes.json"` → `parents[4] / "knowledge-base" / "config" / "knowledge_scopes.json"` (depth −1 **and** new dir).
- `backend/app/platform/config/platforms.py:23`: `parents[5]` → `parents[4]` (platforms.json stays in root `config/`).
- `backend/app/platform/config/settings.py:29`: `DEFAULT_OBI_IDENTITY_PATH` `parents[5]` → `parents[4]` (obi_identity.md stays in root `config/`).
- `.env.example`: comment line 63 (`infra/foundation/init/01-roles.sql`) and lines 129 (stale `apps/automation/config/...`) — comment-only, update for accuracy.

## .claude / CLAUDE.md path strings — Step 5 (see `inventory-parts/08-claude-docs.md`) — 16 hits / 8 files
- **CRITICAL (guard hooks):** `agents/obi-tester.md:12`, `obi-auditor.md:13`, `obi-implementer.md:13` hardcode `$CLAUDE_PROJECT_DIR/apps/automation/tools/agent_guard.py` → `backend/tools/agent_guard.py`, else substep-locking breaks.
- Skills `obi-change` (13,25,26), `obi-audit` (4,10), `obi-verify` (8,14,17): `apps/automation` / `cd apps/automation` / `tools/panel.py` / `tools/brief.py` → backend paths.
- `agents/obi-auditor.md:19`, `obi-implementer.md:18`: panel/brief refs.
- `.claude/settings.local.json`: 1 `apps/automation` ref.
- **DEFER to 1.1.3:** `CLAUDE.md:55` (structure prose). Only path strings change now.

## pyproject / uv workspace — Step 4 (see `inventory-parts/07-python-config.md`)
- No root pyproject / `[tool.uv]` today; sole `uv.lock` at `apps/automation/uv.lock`.
- Add new root `pyproject.toml` with `[tool.uv.workspace] members = ["backend", "knowledge-base"]`; add `obi-knowledge-base` to backend `[project].dependencies` + `[tool.uv.sources] obi-knowledge-base = {workspace = true}`; add `knowledge-base/pyproject.toml` (dist `obi-knowledge-base`, hatch `packages=["schema"]`, sqlalchemy+pgvector pins). `uv sync` consolidates the lock.
- Backend `pyproject.toml`: existing `packages=["app"]`, `testpaths`, pyright `include=["app"]` stay valid (inner `app/` kept). `.venv` will be recreated by `uv sync` (current one has a stale baked path from a folder rename).

## Leftover files not owned by another bucket — Step 5 (see `inventory-parts/10-catchall.md`)
- `README.md` (root): 7 tree/setup lines (`apps/`, `infra/foundation/`, `apps/automation`, `apps/web`).
- `tests/TESTING.md`: 6 lines documenting `apps/web`/`apps/automation` test locations.
- `.gitignore`: 4 `apps/web/...` ignore paths → `frontend/...`.
- `config/platforms.json`: `_readme` self-reference to `config/knowledge_scopes.json` → knowledge-base path.
- Under `docs/` (excluded from the proof grep, so non-blocking, but worth fixing): `docs/OBI-RAG-SYSTEM-A-Z.md`, `docs/runbooks/*`, `docs/adr/0007`, `docs/adr/0010`.

## Proof grep exclusions
The Step-7 grep excludes `.git, node_modules, .venv, docs/archive, final_docs`. Note it does **not** exclude `docs/` broadly — but the plan's proof grep string does exclude `docs/archive` only; path strings under `docs/` will be fixed where they are code-relevant to keep the grep clean where required.

---
## Break-it check result (Step 8)
Reverted one import in `backend/app/platform/jobs/queue.py` (`from schema.models import` → `from app.platform.db.models import`). `make test-unit` failed at collection with `ModuleNotFoundError: No module named 'app.platform.db'` (2 collection errors, e.g. `app/tests/test_cm_root_wiring.py`). Restored the `schema.*` import → `make test-unit` = 536 passed. The move is load-bearing: the old import path is gone and the new one is the only one that resolves.

## What actually changed vs the plan (deviations, recorded honestly)
1. **db config decoupling (owner-approved).** `schema/engine.py` + `schema/models.py` stopped importing `app.platform.config`; new `knowledge-base/schema/settings.py` (`KbSettings`, uncached `get_kb_settings`) reads the same env + .env. `alembic/env.py` reads the URL from `schema.settings` too. This is a logic change beyond "rename-only," required by the one-way rule + the alembic relocation.
2. **`get_kb_settings` is deliberately uncached** so the test harness only clears the engine caches (which it already did) to redirect `DATABASE_URL` per test — otherwise 84 db tests failed against the wrong DB.
3. **db tests relocated to `backend/tests/schema/`** (not into knowledge-base) to stay in the collected suite; their repo-root computation became `parents[3]/"knowledge-base"` and targets point at `knowledge-base/{schema,migrations}`.
4. **Path-depth fixes (code, not just strings):** `knowledge_scopes.py`/`platforms.py`/`settings.py` `parents[5]→parents[4]` (+ `config→knowledge-base/config` for the tag list); `panel.py`/`setup_supabase.py` repo-root `parents[3]→parents[2]`; `test_cm_contracts`/`test_token_claims` `parents[6]→parents[5]`; `test_cm_tokens`/`test_cm_infra` `parents[4]→parents[3]`; frontend `platforms.ts` 5→4 `../`, `knowledge-scopes.test.ts` 6→5 `../` + `knowledge-base/config`. Backend `Settings` env_file `../../.env`→`../.env`.
5. **uv:** editable path dependency (`backend` → `../knowledge-base`, `[tool.uv.sources]`), NOT a uv workspace — keeps `backend/.venv` + pyright `venvPath="."` intact. `schema` pinned first-party in both ruff configs.
6. **`git diff -M` is renames + content edits**, not "renames + config only" — because the db package moved and ~80 files changed `app.platform.db.*`→`schema.*` (the spec assumed the shallower `platform.db`).
7. **Proof grep** enforced over code/config (also excluding `docs/`): the design page + append-only history keep old paths and can't be rewritten. One intentional residual: `CLAUDE.md:55` (self-deleting note, 1.1.3).
8. **Lint improved, not regressed:** 45→19 ruff, 11→0 unformatted (touched files cleaned per CLAUDE.md); pyright unchanged 57.
