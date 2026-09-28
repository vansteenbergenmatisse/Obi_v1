# Runbook · Deploy the Obi backend to Railway (webhook-driven), and roll back

The backend goes online so Confluence Cloud webhooks reach `POST /confluence/events` and drive
ingestion. The **frontend and knowledge editing stay local**; `knowledge-base/` still ships *inside*
the backend image (the backend imports `schema` from it and reads its config JSON at boot). Postgres
stays on Supabase (already provisioned + migrated).

Related runbooks: `deploy-readiness-scope-rls.md` (the blocking RLS gate), `supabase-vector-store-cutover.md`
(the DB cutover), `chat-api-key-rotation.md`.

## Deploy unit

Repo-root `Dockerfile` (build context = repo root) copies `backend/` + `knowledge-base/` + `config/`
as siblings under `/app`, so the `schema` import and the `parents[4]` config-path resolution work
unchanged. `railway.json` pins the Dockerfile builder, `numReplicas: 1`, and `/health` as the
healthcheck. **Run exactly one instance** — the APScheduler worker, rate limiter, idempotency cache
and answer cache are all in-process.

## Before you deploy — owner inputs required

1. **Production `platforms.json`** with ≥1 active platform whose issuer + JWKS URL are real HTTPS
   (non-loopback). Outside an offline env the app **fails to boot** without this.
   **Done (temporary):** the committed file now has an active `obi-test` platform whose issuer is our
   Supabase Auth (`https://<project-ref>.supabase.co/auth/v1`), so the backend boots in production
   before datahub is live. `datahub` is inactive (its TODO placeholders are kept for the swap);
   `mews`/`toast`/`opera-cloud` stay inactive. **obi-test is temporary — remove it once datahub is
   live** (see "Swapping obi-test → datahub" below). Because obi-test uses Supabase Auth as the
   issuer, **turn off public sign-ups in Supabase Auth** — anyone who can sign up gets a token from
   this issuer.
2. **Embedding trio** — `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` / `EMBEDDING_DIM` must match the
   index already built in the Supabase DB. **Confirmed from the working `.env`:**
   `openai` / `text-embedding-3-large` / `3072`. Set these exact values in Railway; do not rely on
   the code defaults (Voyage/1024).
3. **Confluence webhook signing** — confirm Confluence Cloud can send `X-Hub-Signature-256` =
   HMAC-SHA256(raw body) with `CONFLUENCE_WEBHOOK_SECRET` (cross-check the local tunnel test).
4. **Supabase DSNs** (owner + `rag_reader`) and all prod API keys.

## Swapping obi-test → datahub (when datahub is live, Phase 4.x)

`obi-test` is a temporary bridge so production can boot before datahub exists. To retire it:

1. In `knowledge-base/config/platforms.json`, fill datahub's real `issuer`, `jwks_url` and `domains`
   (replace the `TODO until 4.x` placeholders) and set `datahub` `"active": true`.
2. Delete the `obi-test` entry and delete the `obi-test is a TEMPORARY active platform …` sentence
   from the `_readme`.
3. Validate under production before shipping:
   `ENV=production PLATFORMS_PATH=<abs path to platforms.json> uv run python -c "from app.platform.config.settings import Settings; print(Settings().platform_registry.active_platforms())"`
   — expect `['datahub']` and no raise. (Print only the list, never the Settings object.)
4. Run `uv run pytest -q app/platform/config/tests app/features/rag_agent/tests` — the guard tests
   are decoupled from the committed file, so they stay green; the two `..._real_file_...` tests in
   `test_platforms.py` read datahub via `by_issuer` and continue to pass.
5. If public Supabase sign-ups were disabled only for obi-test, decide whether to keep them off.
6. Push to `main` and redeploy.

## Environment variables (set as Railway service variables — never in the image or git)

Fail-closed / load-bearing:

| Var | Value / note |
|---|---|
| `ENV` | `production` (a real value — empty/`dev`/`staging` are treated as production anyway) |
| `DATABASE_URL` | Supabase owner DSN, `postgresql+psycopg://…`, **port 5432** (not 6543) |
| `DATABASE_READER_URL` | the `rag_reader` DSN — **required**, engine fails closed if empty |
| `CHAT_API_KEY` | shared secret with the frontend proxy (must match `frontend/.env.local`) |
| `CONFLUENCE_WEBHOOK_SECRET` | webhook HMAC secret |
| `ANTHROPIC_API_KEY`, embedding + reranker keys | the providers actually used in prod |
| `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` / `EMBEDDING_DIM` | must match the built index |
| `ENABLE_BACKGROUND_JOBS` | `true` — without it, webhooks enqueue jobs nothing drains |
| `PLATFORMS_PATH` | optional; only if not using the in-image `knowledge-base/config/platforms.json` |

Leave `DEV_RECONCILE_INTERVAL_SECONDS` **unset** (that is the "every 30 seconds" fast poll). Defaults
keep the cheap 5s local job-drain (`WORKER_TICK_SECONDS`) and a daily reconcile backstop
(`LIGHTWEIGHT_RECON_CRON`) — the daily one is the only job that reaches out to Confluence.

## Deploy steps

1. **Local gate (before touching infra):** `make check` green; `uv run ruff check . && uv run ruff format --check . && uv run pyright` no worse than baseline.
2. **Build sanity (optional, done once):** `docker build -t obi-backend .` from repo root; run with `-e ENV=local` and confirm `GET /health` 200.
3. **Readiness gate against the prod DB (blocking):**
   `ENV=… uv run python scripts/setup_supabase.py check-deploy-readiness` exits 0, and
   `verify-isolation` passes. See `deploy-readiness-scope-rls.md`.
4. **Create the Railway service** from this repo (Dockerfile builder), set all env vars above, deploy.
5. **Post-boot check:** `GET /health` returns 200 with the right `ENV` and scope list; logs show
   `platform_registry_loaded` and `Application startup complete`, no reader/registry fail-closed error.
6. **Register the Confluence webhook** at `https://<railway-url>/confluence/events` (page + label
   events) with the shared secret.
7. **Live smoke test:** add label `obi-toast-test` to a known page, then
   `DATABASE_URL=<supabase> uv run python scripts/smoke_webhook.py <page_id> --require-tag obi-toast-test`.
   Paste the PASS output into the deploy PR.
8. **Point the local frontend** at the backend: set `AUTOMATION_API_BASE_URL` + matching `CHAT_API_KEY`
   in `frontend/.env.local`.

## Rollback

- **Bad deploy:** Railway → roll back to the previous deployment (previous image). The app is stateless
  besides the DB.
- **Ingestion misbehaving:** set `ENABLE_BACKGROUND_JOBS=false` to pause the worker without dropping
  enqueued jobs (enqueue is `ON CONFLICT DO NOTHING`, claim is `FOR UPDATE SKIP LOCKED` — idempotent),
  or disable the Confluence webhook to stop new events. Re-enable to resume; unprocessed jobs drain.
- **Never** run the 0009 migration downgrade on Supabase and **never** disable row security (root
  `CLAUDE.md` rule #1). Fix the schema forward with a new migration, not a downgrade against prod.

## Scaling note (deferred)

Horizontal scale needs a shared store for the rate limiter / caches and moving the worker out of the
web process. Not needed at current scale; keep a single instance until it is.
