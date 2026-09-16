# Omniboost RAG — developer task runner.
#
# Python tasks run inside the automation venv at apps/automation/.venv, created
# by `uv venv` (see README Quickstart). `uv run` resolves that venv when invoked
# from apps/automation.

AUTOMATION := apps/automation
COMPOSE := infra/foundation/docker-compose.yml
PG_CONTAINER := omniboost_rag_pg
# The local compose Postgres, pinned explicitly (substep 0.5.1/harness.md) so `test-db` can never
# pick up a developer's root .env DATABASE_URL (which may point at a live Supabase project for
# other workflows) — matches docker-compose.yml's POSTGRES_USER/PASSWORD/DB and host port 5434.
DB_URL_LOCAL := postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag

.PHONY: up down migrate test test-unit test-db test-ui eval boundaries check web-dev fmt reingest

## up: start Postgres (pgvector) in the background.
up:
	docker compose -f $(COMPOSE) up -d

## down: stop Postgres.
down:
	docker compose -f $(COMPOSE) down

## migrate: apply Alembic migrations to head.
migrate:
	cd $(AUTOMATION) && uv run alembic upgrade head

## test: run the automation test suite (the pre-0.5.1 umbrella; kept working as-is).
test:
	cd $(AUTOMATION) && uv run pytest

## test-unit: fakes only, no database, no live marker (substep 0.5.1 / harness.md).
## Every test NOT marked `db` — the reranker, embedder, Claude client and Confluence
## gateway are fakes; nothing touches a network or a real Postgres.
test-unit:
	cd $(AUTOMATION) && uv run pytest -m "not db"

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
	cd $(AUTOMATION) && DATABASE_URL=$(DB_URL_LOCAL) uv run alembic upgrade head
	cd $(AUTOMATION) && DATABASE_URL=$(DB_URL_LOCAL) uv run pytest -m db; \
	status=$$?; \
	$(MAKE) -C "$(CURDIR)" down; \
	exit $$status

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

## web-dev: run the Next.js dev server.
web-dev:
	pnpm --filter web dev

## fmt: format and lint-fix the automation code with Ruff.
fmt:
	cd $(AUTOMATION) && uv run ruff format . && uv run ruff check --fix .
