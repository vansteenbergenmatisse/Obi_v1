# backend/ · ownership and shared contracts

Read the root `CLAUDE.md` first — it is authoritative for the whole repo. This file states only what
`backend/` owns and how it couples to the other roots, so a session touching backend code knows the
boundaries before editing.

## What this folder owns

The FastAPI application (`app/main.py` is wiring only) and its **in-process ingestion worker**:

- `app/features/confluence_sync/` — stages 1–2: webhook receiver, event ledger, job queue + worker, sweeps, label→scope.
- `app/features/ingestion/` — stages 3–4: normalize, chunk, contextualize, attachments, embed, version, swap, GC.
- `app/features/retrieval/` — hybrid search, fusion, permissions, rerank, trace writes.
- `app/features/rag_agent/` — the `/chat` endpoint, token/key checks, limits, refusal, generation, citations, prompts. **Every prompt lives here — no prompt text anywhere else.**
- `app/features/evaluation/` — the eval runner, metrics, datasets.
- `app/platform/` — technical capabilities that import no feature (API clients, `config/settings.py`, the job queue, logging).
- `app/shared/` — tiny cross-feature primitives (hashing, rate limiter, TTL cache).
- `scripts/` — operator tools (Supabase setup + isolation, readiness gate, seeds, sweeps, key rotation, `smoke_webhook.py`); `tools/` — repo tooling (`check_feature_boundaries.py`); `tests/` — the backend suite.

## Contracts it shares with the other roots

- **Depends on `knowledge-base/` (upward-facing, hard):** imports the `schema` package (editable path dep, `pyproject.toml` → `../knowledge-base`) for the DB engine/models/enums/RLS; reads `knowledge-base/config/platforms.json` + `knowledge_scopes.json` at boot (via `Path(__file__).resolve().parents[4]`); its Alembic migrations live under `knowledge-base/migrations/`. **The backend cannot build, boot, or migrate without `knowledge-base/` present as a sibling.** It ships *with* the backend in the deploy image.
- **Serves the frontend over HTTP:** the frontend's Next.js proxy calls `POST /chat` server-to-server with the shared `CHAT_API_KEY`. The wire contract is `packages/contracts/src/openapi/chat.yaml` (source of truth; the backend does not import the TS package).
- **Never imports `frontend/`** — the `make boundaries` gate fails the build on any backend→frontend import.

## Deploy facts

- Deployed to **Railway** as a single service from the repo-root `Dockerfile` (build context = repo root). Config: `railway.json`.
- **Run exactly one instance** — the APScheduler worker, rate limiter, idempotency cache and answer cache are all in-process/in-memory.
- Endpoints exposed publicly: `POST /confluence/events` (HMAC), `POST /chat` (`CHAT_API_KEY` + per-user JWT), `GET /health` (liveness).
- Webhook-driven ingestion needs `ENABLE_BACKGROUND_JOBS=true`; leave `DEV_RECONCILE_INTERVAL_SECONDS` unset (no fast polling). See `docs/runbooks/railway-backend-deploy.md`.
- Secrets come from the host env, never the image or git. `EMBEDDING_PROVIDER/MODEL/DIM` must match the index built in the target DB.

## Commands

Run from `backend/` with `uv run`. `make check` (boundaries + tests) is the enforced gate before any commit; `make test`, `make eval`, `make boundaries` as documented in the root `CLAUDE.md`.
