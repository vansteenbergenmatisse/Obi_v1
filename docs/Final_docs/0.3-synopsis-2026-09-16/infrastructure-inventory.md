# 0.3.3 — Infrastructure inventory (read-only)

Assignment: how the code runs today, one line per question, every line backed by file:line. Proof
standard: an engineer new to the repo should be able to run the tests from this file alone.

## 1. Package managers and lock files

- **JavaScript workspace: pnpm**, pinned `packageManager: "pnpm@10.33.2"` at `package.json:6`.
  Workspace members are `apps/web` and `packages/*` per `pnpm-workspace.yaml:1-3` (`apps/automation`
  is deliberately not a member — it is the Python app). Lockfile `pnpm-lock.yaml` exists at the repo
  root (confirmed present, 99,885 bytes, last modified 2026-09-12).
- **Python app: uv**, dependencies declared in `apps/automation/pyproject.toml:1-20` (`[project]`
  block: fastapi, uvicorn, sqlalchemy, alembic, psycopg, pgvector, etc.). Lockfile
  `apps/automation/uv.lock` exists (confirmed present, 257,894 bytes). The checked-in venv itself was
  built by uv: `apps/automation/.venv/pyvenv.cfg:3` reads `uv = 0.11.28`.
- Root task runner `package.json:9-12` only orchestrates `turbo run dev/build/lint` (`turbo.json:1-15`)
  across the pnpm workspace; it does not touch the Python app.

## 2. Every make target in the root Makefile

Source: `Makefile:1-57`. `AUTOMATION := apps/automation` (`Makefile:7`), `COMPOSE :=
infra/foundation/docker-compose.yml` (`Makefile:8`).

| target | command | file:line |
|---|---|---|
| `up` | `docker compose -f $(COMPOSE) up -d` | `Makefile:13-14` |
| `down` | `docker compose -f $(COMPOSE) down` | `Makefile:17-18` |
| `migrate` | `cd $(AUTOMATION) && uv run alembic upgrade head` | `Makefile:21-22` |
| `test` | `cd $(AUTOMATION) && uv run pytest` | `Makefile:25-26` |
| `eval` | `cd $(AUTOMATION) && uv run python -m app.features.evaluation.run_baseline` | `Makefile:31-32` |
| `boundaries` | `cd $(AUTOMATION) && uv run python tools/check_feature_boundaries.py` | `Makefile:35-36` |
| `check` | `check: boundaries test` (runs `boundaries` then `test`, in that order) | `Makefile:40` |
| `reingest` | `cd $(AUTOMATION) && uv run python scripts/run_reconciliation_once.py` | `Makefile:47-48` |
| `web-dev` | `pnpm --filter web dev` | `Makefile:51-52` |
| `fmt` | `cd $(AUTOMATION) && uv run ruff format . && uv run ruff check --fix .` | `Makefile:55-56` |

Drift note: the `eval` target's own comment says the module "may fail until that module exists"
(`Makefile:28-30`), but `apps/automation/app/features/evaluation/run_baseline.py` already exists
(confirmed present) — the comment is stale, the target should run.

## 3. CI file(s), jobs, triggers

**None exist.** Searched the whole repository (excluding `node_modules` and `.venv`):
- `find . -path "*/.github/*"` (repo-wide) — zero hits, no `.github` directory anywhere.
- `find . -iname "*.yml" -not -path "*/node_modules/*" -not -path "*/.venv/*"` — the only hit in the
  entire tree is `infra/foundation/docker-compose.yml`; no workflow YAML exists.
- No `.pre-commit-config.yaml` anywhere.
- `.git/hooks/` contains only Git's own `*.sample` templates (no installed hook), confirmed by listing
  the directory — every file present ends in `.sample`.

There is no CI job, so there is nothing to report for triggers or jobs. `_OFFLINE_ENVS` in
`apps/automation/app/platform/config/settings.py:24` already anticipates a `"ci"` environment value,
but no pipeline sets `ENV=ci` anywhere in the repo.

## 4. Dockerfiles and compose files

**One compose file, no Dockerfiles.**
- `infra/foundation/docker-compose.yml:1-27` — one service, `postgres`, image
  `pgvector/pgvector:pg16@sha256:1d5335...` pinned by digest (`infra/foundation/docker-compose.yml:7`),
  env `POSTGRES_USER=rag`/`POSTGRES_PASSWORD=rag`/`POSTGRES_DB=omniboost_rag`
  (`infra/foundation/docker-compose.yml:10-12`), host port `5434` → container `5432`
  (`infra/foundation/docker-compose.yml:13-15`), named volume `rag_pg_data`
  (`infra/foundation/docker-compose.yml:16-17,26-27`), and a bootstrap-script mount
  `./init:/docker-entrypoint-initdb.d:ro` (`infra/foundation/docker-compose.yml:19`) that runs
  `infra/foundation/init/01-roles.sql:1-24` (creates the non-owner `rag_reader` role) on first volume
  init. This is started by `make up` (`Makefile:12-14`).
- No `Dockerfile` for the backend or the frontend exists anywhere in project code. Searched
  `find . -iname "Dockerfile*" -not -path "*/node_modules/*"` repo-wide — the only hits are inside
  `apps/automation/.venv/lib/python3.12/site-packages/pyright/.../typeshed-fallback/stubs/` (a vendored
  third-party stub package, not project code).

## 5. Where the backend and the widget run

- **Backend, local dev**: `cd apps/automation && uv run uvicorn app.main:app --port 8000`
  (`docs/rag/PLAN.md:246`, also `docs/rag/PLAN.md:2916`). The FastAPI app object is built at module
  load by `create_app()`: `apps/automation/app/main.py:220` (`app = create_app()`); no root route is
  defined, `/docs` is the documented liveness check (`docs/rag/PLAN.md:2917`). No `Makefile` target
  runs this command directly — it is not wired into `make` (checked: `Makefile:1-57` has no `uvicorn`
  or backend-serve target; `web-dev` only starts the Next.js app).
- **Backend, deploy target**: none configured in this repo. `docs/rag/PLAN.md:1201-1202` records the
  decision explicitly: "Deploy target = AWS, committed but deferred. Not now; not Vercel or any other
  platform... For now the app runs locally (backend local is fine)." No Dockerfile, Procfile,
  `fly.toml`, or `render.yaml` exists at the repo root (checked, no hits for any of those names).
- **Widget, local dev**: `pnpm --filter web dev` (`Makefile:51-52`; `apps/web/package.json:7`,
  `"dev": "next dev"`), observed running on `:3000` per `docs/rag/PLAN.md:2919`.
- **Widget, build**: `apps/web/package.json:8` (`"build": "pnpm run build:obi && next build"`), where
  `build:obi` (`apps/web/package.json:9`) bundles the embed loader with esbuild into
  `apps/web/public/obi.js` (gitignored, `.gitignore:43`); `"start": "next start"`
  (`apps/web/package.json:10`).
- **Widget, deploy target**: none configured. Same `docs/rag/PLAN.md:1201` line rules out Vercel by
  name for the whole app; no `vercel.json` exists at the repo root (checked, no hit).

## 6. How secrets reach each environment (mechanism only, no values)

- **Backend, local**: `pydantic-settings` reads a `.env` file — `env_file=(".env", "../../.env")` at
  `apps/automation/app/platform/config/settings.py:34`, so either a repo-root `.env` or an
  `apps/automation/.env` is picked up. The module docstring states the production mechanism:
  "real deployments inject env vars directly" (`apps/automation/app/platform/config/settings.py:3-4`)
  — no specific injection mechanism (vault, secrets manager) is named anywhere in code. The template
  with placeholder values is `.env.example` (e.g. `.env.example:19` `ANTHROPIC_API_KEY=changeme`); the
  real `.env` is git-ignored (`.gitignore:20-21`, entries `.env` and `.env.local`).
- **Frontend, local**: Next.js does not read the repo-root `.env` (`apps/web/.env.example:1-2`,
  `README.md:75-76`), so it has its own `apps/web/.env.local`, read via `process.env` at
  `apps/web/src/platform/automation-api/client.ts:24` (`CHAT_API_KEY`) and `:28-29`
  (`AUTOMATION_API_BASE_URL`, `AUTOMATION_API_TIMEOUT_MS`). Template at `apps/web/.env.example:4-8`
  (`CHAT_API_KEY`) and `:9-10` (`AUTOMATION_API_BASE_URL`); the value must be manually copied to match
  the backend's `chat_api_key` setting (`apps/automation/app/platform/config/settings.py:150`), per
  `apps/web/.env.example:6-7` and `README.md:75-79` — a manual shared-secret copy, not a shared vault.
- **CI secrets**: not applicable — no CI file exists to hold any (see §3).
- **Vault / secrets manager**: none found. Searched for "vault", "secretsmanager", "secrets-manager",
  "kms" across `apps/automation/app` and `apps/web/src` — no hits in either tree.
- **Supabase cutover secret handling**: the reader DSN password is generated by
  `apps/automation/scripts/setup_supabase.py` and written straight into `.env` as
  `DATABASE_READER_URL`, "password generated, never printed"
  (`docs/runbooks/supabase-vector-store-cutover.md:21-22,58`) — same `.env`-file mechanism as local
  dev, no separate secret store.

## 7. Does a staging environment exist?

**No staging deploy environment or config exists in this repo.** `env=staging` is only a recognized
settings *value* exercised by parametrized tests — `docs/rag/PLAN.md:4735-4737` describes a test
matrix where "3 non-offline envs (production/staging/prod)" must fail closed without a reader URL —
there is no `.env.staging`, CI job, or deploy script anywhere that actually sets `ENV=staging`. The
current root `.env` is `ENV=local` (`.env:86`). A staging embed domain is still an open question, not
a built environment: `docs/rag/PLAN.md:487` asks "embed domain for staging/prod (`obi.omniboost.com`?)
— local-only otherwise." Separately, a **live database** beyond local does exist: `docs/rag/PLAN.md:
1183-1185` records reader-RLS migration `0009` "✅ APPLIED to live Supabase" (dated 2026-09-09 in the
surrounding section) — but the repo calls this the **production** vector store by decision
(`docs/adr/0013-Managed-Postgres-Vector-Store-And-Force-RLS-Drop.md:1,34`), not a staging tier, and the
running application itself is still described as local-only against it (`docs/rag/PLAN.md:1202`,
"the app runs locally").

## 8. Where the local Postgres with pgvector comes from, and its migration head

- Source: `infra/foundation/docker-compose.yml:1-27`, one `postgres` service, image
  `pgvector/pgvector:pg16` pinned by digest `sha256:1d5335...` (`infra/foundation/docker-compose.yml:7`,
  comment at `:3-6` states this is pgvector 0.8.5). Started by `make up` (`Makefile:12-14`), stopped by
  `make down` (`Makefile:16-18`), migrated to head by `make migrate` (`Makefile:20-22`).
- Migration head: 12 numbered files exist, `0001` through `0012`
  (`apps/automation/alembic/versions/0001_core_schema.py` through
  `apps/automation/alembic/versions/0012_widen_document_version_idem.py`, confirmed by directory
  listing). The head is `0012_widen_document_version_idem`, which chains from `0011` —
  `apps/automation/alembic/versions/0012_widen_document_version_idem.py:20-22` reads `Revision ID:
  0012_widen_document_version_idem` / `Revises: 0011_query_trace_subject_hash`.

## Environments

| environment | what exists | evidence | what's missing |
|---|---|---|---|
| **local** | Full stack runs here today: Postgres via docker-compose, backend via `uv run uvicorn`, widget via `pnpm --filter web dev`, `.env` present with `ENV=local` | `infra/foundation/docker-compose.yml:1-27`; `docs/rag/PLAN.md:246,2916,2919`; `.env:86` | Nothing — this is the only environment with working dev tooling in the repo |
| **staging** | Not built. Only a recognized settings value in tests, and an open question about an embed domain | `docs/rag/PLAN.md:4735-4737,487` | `.env.staging`, any CI job, any deploy script, any staging app deployment |
| **production** | Database decision made and (per PLAN.md, dated 2026-09-09) partially applied live on Supabase; app deploy target decided (AWS) but not built | `docs/adr/0013-Managed-Postgres-Vector-Store-And-Force-RLS-Drop.md:1,34`; `docs/runbooks/supabase-vector-store-cutover.md:1-9`; `docs/rag/PLAN.md:1183-1185,1201-1202` | No Dockerfile, deploy script, or CI for either app; local migration head (`0012`) is 3 revisions ahead of the last PLAN.md-recorded live-applied head (`0009`) — current live head needs a live check, not provable from files |

## Not found

- **No CI workflow file.** Searched: `find . -path "*/.github/*"` (repo-wide, excludes `node_modules`)
  — no hits; `find . -iname "*.yml" -not -path "*/node_modules/*" -not -path "*/.venv/*"` — only
  `infra/foundation/docker-compose.yml`; no `.pre-commit-config.yaml`; `.git/hooks/` has only
  `*.sample` files.
- **No Dockerfile for the backend or frontend.** Searched: `find . -iname "Dockerfile*" -not -path
  "*/node_modules/*"` — only hits are vendored `pyright` typeshed stubs under
  `apps/automation/.venv/lib/python3.12/site-packages/pyright/...`, not project code.
- **No deploy-platform config for either app** (Vercel/Render/Fly/Procfile/etc). Searched: `find .
  -maxdepth 1 -iname "vercel.json"`, `-iname "render.yaml"`, `-iname "fly.toml"`, `-iname "Procfile"`
  at repo root — no hits. The only concrete statement found is the deferred-AWS decision at
  `docs/rag/PLAN.md:1201-1202`, with no config file to inspect alongside it.
- **No vault / secrets-manager integration.** Searched: grep (case-insensitive) for "vault",
  "secretsmanager", "secrets-manager", "kms" across `apps/automation/app` and `apps/web/src` — no
  hits in either tree. The only named mechanism is ".env files locally, env vars injected directly in
  real deployments" (`apps/automation/app/platform/config/settings.py:3-4`), which does not name a
  specific injection mechanism.
- **Current live Supabase migration head cannot be confirmed from files.** `docs/rag/PLAN.md:1183-1185`
  is a point-in-time record (2026-09-09); three more local migrations (`0010`, `0011`, `0012`) exist
  since then with no later PLAN.md entry confirming they were applied live. Confirming this needs
  `uv run alembic current` run against the live Supabase DSN
  (`docs/runbooks/supabase-vector-store-cutover.md:52-53`) — out of scope for a read-only file audit
  (needs live).
- **`pnpm test:e2e`** (named in the project's `CLAUDE.md` test-levels table as the browser-test
  command) does not exist in this repo: no `test:e2e` script in `package.json` or
  `apps/web/package.json` (checked both in full), and no Playwright config anywhere (`find . -iname
  "playwright*" -not -path "*/node_modules/*"` — no hits). This is a `CLAUDE.md`-vs-repo drift, not a
  design-page contradiction, recorded here for a human to pick up.

## Design-page cross-check

The only design panel naming this folder is `cm-infra` (`python3 apps/automation/tools/panel.py
cm-infra`): "docker-compose | pgvector image pinned to 0.8.x" and "Use | local development and the
test database; production is Supabase." Both claims match the code exactly —
`infra/foundation/docker-compose.yml:3-7` (pinned pgvector 0.8.5 by digest) and the production-is-
Supabase decision at `docs/adr/0013-Managed-Postgres-Vector-Store-And-Force-RLS-Drop.md:1,34`. No
contradiction found for `cm-infra`. No other panel names CI, Docker, deploy targets, or a staging
environment (`--grep staging` returns only `i4-staging`, a `document_version` row-state panel unrelated
to infrastructure; `--grep deploy` returns only `ks-deploy`, about shipping a knowledge-scope JSON
file, not an infra deploy). One structural note carried over from the project's own `CLAUDE.md`
(`CLAUDE.md:11`): it names `docs/design/` as the design page's location, but no `docs/design/`
directory exists in this repository — this was already flagged by the prior 0.3 audit
(`docs/Final_docs/0.3-code-vs-design-audit-2026-09-14/packages-config-infra-docs.md:48`) and still
holds; the actual design-page source `panel.py` reads is `docs/Final_docs/obi-rag-system-flow
(3).html`.
