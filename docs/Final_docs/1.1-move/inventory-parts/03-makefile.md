# 03 · Makefile — path inventory for the 1.1 folder move

Read-only inventory of `Makefile` (root). Every line that names a path/dir affected by the move, grouped by variable definitions then by target. Moves in scope:

- `apps/automation` → `backend`
- `infra/foundation` → `knowledge-base/local`
- alembic migrations → `knowledge-base/migrations/`
- `config/knowledge_scopes.json` → `knowledge-base/config/`
- tools stay under `backend/tools/` (i.e. relative `tools/` under `$(AUTOMATION)` is unchanged)

## Header comments (not a target, but stale after move)

- `Makefile:3: # by \`uv venv\` (see README Quickstart). \`uv run\` resolves that venv when invoked` — comment on line 3/4 pair.
- `Makefile:3: # Python tasks run inside the automation venv at apps/automation/.venv, created` → new value: `backend/.venv`. **NEEDS CHANGE (comment text).**
- `Makefile:4: # from apps/automation.` → new value: `from backend.` **NEEDS CHANGE (comment text).**

## Variable definitions

- `Makefile:7: AUTOMATION := apps/automation` → new value: `AUTOMATION := backend`. **NEEDS CHANGE.**
- `Makefile:8: COMPOSE := infra/foundation/docker-compose.yml` → new value: `COMPOSE := knowledge-base/local/docker-compose.yml`. **NEEDS CHANGE.**
- `Makefile:9: PG_CONTAINER := omniboost_rag_pg` → container name, not a repo path. **No change** (must still match the moved docker-compose.yml's container_name).
- `Makefile:13: DB_URL_LOCAL := postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag` → a DB connection string, not a repo path. **No change.**

## Targets

### up
- `Makefile:19: 	docker compose -f $(COMPOSE) up -d` — path via `$(COMPOSE)`. **No literal edit** (auto-follows COMPOSE line 8).

### down
- `Makefile:23: 	docker compose -f $(COMPOSE) down` — path via `$(COMPOSE)`. **No literal edit** (auto-follows line 8).

### migrate
- `Makefile:30: 	cd $(AUTOMATION) && DATABASE_URL=$(DB_URL_LOCAL) uv run alembic upgrade head` — dir via `$(AUTOMATION)`. **No literal edit** to the line, BUT flag: alembic runs from `backend/`, so with migrations moved to `knowledge-base/migrations/`, alembic's `script_location` (in `alembic.ini`) must resolve to the new path or this target breaks. Behavior-affected by the move even though the Makefile text does not change.

### test
- `Makefile:36: 	cd $(AUTOMATION) && DATABASE_URL=$(DB_URL_LOCAL) uv run pytest` — dir via `$(AUTOMATION)`. **No literal edit** (auto-follows line 7).

### test-unit
- `Makefile:42: 	cd $(AUTOMATION) && uv run pytest -m "not db"` — dir via `$(AUTOMATION)`. **No literal edit** (auto-follows line 7).

### test-db
- `Makefile:51: 	$(MAKE) up` — indirect. **No change.**
- `Makefile:54: 		docker exec $(PG_CONTAINER) pg_isready -U rag -d omniboost_rag ...` — container name, no repo path. **No change.**
- `Makefile:57: 	docker exec $(PG_CONTAINER) psql -U rag -d omniboost_rag -f /docker-entrypoint-initdb.d/01-roles.sql` — the `-f` path is **container-internal** (mounted volume), so the literal stays. BUT flag: the host source of `01-roles.sql` lives under `infra/foundation` and moves to `knowledge-base/local`; the mount is defined in docker-compose.yml (line 8's file), not here. No Makefile edit; move-dependent.
- `Makefile:58: 	cd $(AUTOMATION) && DATABASE_URL=$(DB_URL_LOCAL) uv run alembic upgrade head` — same alembic `script_location` concern as line 30. **No literal edit**, behavior-affected.
- `Makefile:59: 	cd $(AUTOMATION) && DATABASE_URL=$(DB_URL_LOCAL) uv run pytest -m db; \` — dir via `$(AUTOMATION)`. **No literal edit.**
- `Makefile:61: 		$(MAKE) -C "$(CURDIR)" down; \` — indirect. **No change.**

### eval
- `Makefile:75: 	cd $(AUTOMATION) && uv run python -m app.features.evaluation.run_baseline` — dir via `$(AUTOMATION)`; module path is Python dotted, not a repo dir. **No literal edit** (auto-follows line 7).

### boundaries
- `Makefile:79: 	cd $(AUTOMATION) && uv run python tools/check_feature_boundaries.py` — dir via `$(AUTOMATION)`; `tools/` stays under `backend/tools/`, so relative path is still correct after the move. **No change.**

### check
- `Makefile:83: check: boundaries test` — target deps only, no path. **No change.**

### reingest
- `Makefile:91: 	cd $(AUTOMATION) && uv run python scripts/run_reconciliation_once.py` — dir via `$(AUTOMATION)`; `scripts/` stays under `backend/scripts/`. **No change.**

### web-dev
- `Makefile:95: 	pnpm --filter web dev` — pnpm workspace filter, not a filesystem path here. **No change** (depends on the frontend workspace name, not the move).

### fmt
- `Makefile:99: 	cd $(AUTOMATION) && uv run ruff format . && uv run ruff check --fix .` — dir via `$(AUTOMATION)`. **No literal edit** (auto-follows line 7).

## Summary

- Literal-path lines needing an edit: **4** — lines 3, 4 (comments), 7, 8 (variable defs).
- Because targets reference `$(AUTOMATION)` and `$(COMPOSE)`, no target command line needs a literal path edit; they auto-follow lines 7–8.
- Two behavior flags (no Makefile text edit, but the move can break them): alembic `script_location` for `migrate` (line 30) and `test-db` (line 58) once migrations move to `knowledge-base/migrations/`; and the `01-roles.sql` volume mount for `test-db` (line 57), which is defined in the moved docker-compose.yml, not the Makefile.
- `config/knowledge_scopes.json` is not referenced by the Makefile — no line for it.
