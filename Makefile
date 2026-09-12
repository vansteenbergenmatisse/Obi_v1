# Omniboost RAG — developer task runner.
#
# Python tasks run inside the automation venv at apps/automation/.venv, created
# by `uv venv` (see README Quickstart). `uv run` resolves that venv when invoked
# from apps/automation.

AUTOMATION := apps/automation
COMPOSE := infra/foundation/docker-compose.yml

.PHONY: up down migrate test eval boundaries check web-dev fmt reingest

## up: start Postgres (pgvector) in the background.
up:
	docker compose -f $(COMPOSE) up -d

## down: stop Postgres.
down:
	docker compose -f $(COMPOSE) down

## migrate: apply Alembic migrations to head.
migrate:
	cd $(AUTOMATION) && uv run alembic upgrade head

## test: run the automation test suite.
test:
	cd $(AUTOMATION) && uv run pytest

## eval: run the retrieval evaluation baseline.
## (app.features.evaluation.run_baseline is created by another worker; this
##  target may fail until that module exists.)
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
