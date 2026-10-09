# frontend/ · ownership and shared contracts

Read the root `CLAUDE.md` first — it is authoritative for the whole repo. This file states only what
`frontend/` owns and how it couples to the backend.

## What this folder owns

The Next.js app — the only place UI lives.

- `src/features/chat/` — the widget: `ui/`, `api/`, `server/` (the proxy route that adds the host key), `model/`.
- `src/features/embed/` — the embed frame, the iframe bridge, the loader script, and `platforms.ts` (server-side read of the platform allowlist for the embed CSP).
- `src/app/api/chat/` — the thin route entrypoint. `src/components/` — reusable UI shared across features.

## Contracts it shares with the other roots

- **Talks to the backend over HTTP only.** The browser calls the local Next.js proxy; the proxy calls the backend server-to-server. Two env vars in `.env.local` are the contract:
  - `AUTOMATION_API_BASE_URL` — the backend base URL (e.g. the deployed Railway URL, or `http://localhost:8000` locally).
  - `CHAT_API_KEY` — must equal the backend's `CHAT_API_KEY` (the shared proxy secret).
  - The wire shape is `@omniboost/contracts` (`packages/contracts`), imported for TS types (chat + iframe postMessage contracts).
- **Reads `knowledge-base/config/platforms.json`** at request time (server-side, `src/features/embed/platforms.ts`) for the embed CSP `frame-ancestors`. Overridable via `PLATFORMS_PATH`; otherwise it expects `knowledge-base/` as a sibling on disk.
- **Never imports `backend/` source or any `.py` file** — `make boundaries` fails the build otherwise.

## Deploy posture

Locally it runs with `make web-dev`; `AUTOMATION_API_BASE_URL` points it at the backend (local or
the deployed Railway URL). No CORS is involved because calls are server-to-server through the proxy.
Package managers do not mix: `pnpm` here, `uv` for the Python roots.

**Deployed (substep 8.4.3, 2026-10-09):** the frontend runs as the Railway service **`obi-web`** in
the `obi-backend` project — Online, eu-west, at `https://obi-web-production.up.railway.app`, serving
`/obi.js` (deployed origin baked in) and `/embed` (CSP `frame-ancestors` computed from the active
`platforms.json` domains). It is the canonical embed origin handed to platforms (owner decision,
round 2). The service is built by Railway's Railpack (Node) over the whole repo so
`knowledge-base/config/platforms.json` resolves as a sibling. Deploy with
`scripts/deploy-frontend.sh` (it hides the backend-only repo-root `railway.json`/`Dockerfile`/
`.dockerignore` for the upload so Railway builds the web workspace, not the backend image) and
re-prove with `node frontend/scripts/embed-check-live.mjs`. Full detail:
`docs/runbooks/railway-frontend-deploy.md`.
