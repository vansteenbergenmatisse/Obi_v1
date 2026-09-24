# Omniboost RAG — developer task runner.
#
# Python tasks run inside the backend venv at backend/.venv, created
# by `uv sync` (see README Quickstart). `uv run` resolves that venv when invoked
# from backend. The schema package lives in ../knowledge-base (editable path dep).

AUTOMATION := backend
COMPOSE := knowledge-base/local/docker-compose.yml
PG_CONTAINER := omniboost_rag_pg
# The local compose Postgres, pinned explicitly (substep 0.5.1/harness.md) so `test-db` can never
# pick up a developer's root .env DATABASE_URL (which may point at a live Supabase project for
# other workflows) — matches docker-compose.yml's POSTGRES_USER/PASSWORD/DB and host port 5434.
DB_URL_LOCAL := postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag

.PHONY: up down migrate test test-unit test-db test-ui eval boundaries check web-dev api embed-dev tunnel fmt reingest

## up: start Postgres (pgvector) in the background.
up:
	docker compose -f $(COMPOSE) up -d

## down: stop Postgres.
down:
	docker compose -f $(COMPOSE) down

## migrate: apply Alembic migrations to head on the LOCAL pgvector Postgres.
## Pinned to the local URL (like test-db) so a bare `make migrate` can never migrate a
## live Supabase project via a developer's root .env DATABASE_URL. Migrating a live
## project is a deliberate act: run alembic directly with an explicit DATABASE_URL.
migrate:
	cd $(AUTOMATION) && DATABASE_URL=$(DB_URL_LOCAL) uv run alembic -c ../knowledge-base/migrations/alembic.ini upgrade head

## test: run the backend suite then the knowledge base's own standalone suite (the umbrella
## behind `make check`; 1.1.1-fix wires knowledge-base/tests/ in here too so the pre-commit
## gate covers both trees, not just the backend). Pinned to the local URL (like test-db) so
## db-marked tests can never run against a live Supabase project via the root .env
## DATABASE_URL. Run `make up` first for the db tests.
test:
	cd $(AUTOMATION) && DATABASE_URL=$(DB_URL_LOCAL) uv run pytest
	cd knowledge-base && DATABASE_URL=$(DB_URL_LOCAL) uv run pytest

## test-unit: fakes only, no database, no live marker (substep 0.5.1 / harness.md).
## Every test NOT marked `db` — the reranker, embedder, Claude client and Confluence
## gateway are fakes; nothing touches a network or a real Postgres. Runs the architecture
## boundary checker first (ADR-0003 feature rules + the 1.1.2 one-way folder rules) so a
## wrong-way import fails the unit level (and CI, which runs this target). Runs the backend
## suite then the knowledge base's own standalone suite (1.1.1-fix: knowledge-base/tests/,
## run from its own venv so the one-way rule — it imports nothing from the backend — holds).
test-unit: boundaries
	cd $(AUTOMATION) && uv run pytest -m "not db"
	cd knowledge-base && uv run pytest -m "not db"

## test-db: the database suite against the LOCAL pgvector Postgres (substep 0.5.1 /
## harness.md). Starts compose, re-applies the roles/policies init script idempotently
## (covers a volume that predates the rag_reader role), migrates to head, runs every
## `db`-marked test with DATABASE_URL pinned to the local instance (never the root
## .env, which may point at a live project for other workflows), then always tears
## compose back down — exits non-zero on any test failure.
test-db:
	$(MAKE) up
	@echo "test-db: waiting for postgres..."
	@for i in $$(seq 1 30); do \
		docker exec $(PG_CONTAINER) pg_isready -U rag -d omniboost_rag >/dev/null 2>&1 && break; \
		sleep 1; \
	done
	docker exec $(PG_CONTAINER) psql -U rag -d omniboost_rag -f /docker-entrypoint-initdb.d/01-roles.sql
	cd $(AUTOMATION) && DATABASE_URL=$(DB_URL_LOCAL) uv run alembic -c ../knowledge-base/migrations/alembic.ini upgrade head
	cd $(AUTOMATION) && DATABASE_URL=$(DB_URL_LOCAL) uv run pytest -m db; \
	status=$$?; \
	cd "$(CURDIR)/knowledge-base" && DATABASE_URL=$(DB_URL_LOCAL) uv run pytest -m db; \
	kb_status=$$?; \
	$(MAKE) -C "$(CURDIR)" down; \
	if [ $$status -ne 0 ]; then exit $$status; fi; \
	exit $$kb_status

## test-ui: the widget's Playwright browser suite against a stub host page
## (substep 0.5.1 / harness.md). Installs Chromium first (no-op if already present).
test-ui:
	pnpm --filter web exec playwright install --with-deps chromium
	pnpm --filter web test:e2e

## eval: run the retrieval evaluation baseline (substep 0.5.1 / harness.md). The bundled
## datasets (retrieval_smoke, ambiguity, permission, out_of_corpus) already exist and this
## already exits 0 today, printing recall/mrr/hit_rate per dataset plus the saved rerank-lift
## table — the real held-out gold set from PLAN 3.1 will extend, not replace, this.
eval:
	cd $(AUTOMATION) && uv run python -m app.features.evaluation.run_baseline

## boundaries: enforce the feature / platform / shared import architecture.
boundaries:
	cd $(AUTOMATION) && uv run python tools/check_feature_boundaries.py

## check: the machine-enforced gate — architecture boundaries then the tests.
## (Ruff and Pyright are tracked separately at no-regression; see docs/adr.)
check: boundaries test

## reingest: pull edits from live Confluence on demand — a full reconciliation sweep + drain.
## Use this after editing a live Confluence page when the backend runs without background jobs
## (enable_background_jobs=false, the local default) and no webhook is wired: nothing re-pulls
## edits automatically, so run this to re-index them. Refuses against the offline fixture — needs
## live Confluence configured. Re-embeds changed/version-bumped pages (small live embedding spend).
reingest:
	cd $(AUTOMATION) && uv run python scripts/run_reconciliation_once.py

## web-dev: run the Next.js dev server (port 3000). For the EMBED test use `embed-dev` instead —
## the local platform registry pins JWKS on :3100, so :3000 makes JWKS fetch 404 and every token 401.
web-dev:
	pnpm --filter web dev

## api: run the backend (FastAPI) on :8000 for the localhost embed test (docs/Final_docs/brief/localhost-test.md).
## Reads the root .env (ENV=local, PLATFORMS_PATH, CHAT_API_KEY). To use the fully-local pgvector DB
## instead of the .env DATABASE_URL, prefix: `DATABASE_URL=$(DB_URL_LOCAL) make api`.
api:
	cd $(AUTOMATION) && uv run uvicorn app.main:app --port 8000 --reload

## embed-dev: run the frontend on :3100 (NOT :3000) so the local test hosts' JWKS URLs resolve and
## a minted test token verifies. Rebuilds public/obi.js first. Pair with `make api`; then open
## http://localhost:3100/test-hosts/{toast,mews,opera-cloud,multi}. The dev-only scope switcher
## (the header tag icon) stays off here so the embed matches a real embed; prefix
## `NEXT_PUBLIC_SHOW_SCOPE_SWITCHER=true` to bring it back for scope-isolation checks (PLAN 10.8).
embed-dev:
	cd frontend && pnpm run build:obi && pnpm exec next dev --port 3100

## tunnel: expose the local frontend (:3100) on a public HTTPS URL for a self-only "test online".
## Run `make api` and `make embed-dev` first (two other terminals). Starts a cloudflared quick
## tunnel, injects its random hostname into platforms.local.json so the embed CSP/postMessage gate
## accepts it, prints the public /test-hosts/none URL, and restores the registry on Ctrl-C.
tunnel:
	scripts/tunnel-embed-test.sh

## fmt: format and lint-fix the automation code with Ruff.
fmt:
	cd $(AUTOMATION) && uv run ruff format . && uv run ruff check --fix .
