# Runbook — deploy the Obi frontend (`obi-web`) to Railway

Companion to `railway-backend-deploy.md` (which is backend-only and says so). This covers the
Next.js frontend: the chat widget, the `/embed` frame, and the `/obi.js` loader script. Written for
substep **8.4.3 · The frontend deploys on Railway** (design panels em-loader, em-hostbackend).

## Status (2026-10-09)

The frontend **is already deployed and live** as the Railway service **`obi-web`** in the
`obi-backend` project (same project as the backend):

- URL: `https://obi-web-production.up.railway.app` — Online, region **EU West** (next to the
  backend and Supabase `eu-west-1`).
- Serves `/obi.js` (200, with the deployed origin **baked in** at build via esbuild `--define`) and
  `/embed` (200, CSP `frame-ancestors` computed per request from the active `platforms.json`
  domains).
- This is the **canonical embed origin** handed to platforms (owner decision round 2, §D.16; the URL
  choice confirmed 2026-10-09 — use the Railway hostname, not a custom domain, for now). The
  `obi.omniboost.com` host named in the brief/em-loader "Loads from" line remains the eventual
  target; it currently CNAMEs to the main omniboost.com site and does **not** serve `/obi.js`.
- Proof of the live state: `node frontend/scripts/embed-check-live.mjs` → all 7 checks pass; captured
  output in `docs/Final_docs/5-integration-context/embed-live-check-output.txt`.

### Service variables observed on `obi-web` (keys only — values never read or printed)

`APP_ENV`, `AUTOMATION_API_BASE_URL` (the backend URL), `CHAT_API_KEY` (shared proxy secret, must
equal the backend's), `OBI_ORIGIN`, `OBI_INTERNAL_ORIGIN`, `PORT`, `RAILPACK_NODE_VERSION`, plus
Railway's own `RAILWAY_*` and the `RAILWAY_SERVICE_OBI_BACKEND_URL` reference. No `PLATFORMS_PATH`
is set, so `platforms.ts` resolves `knowledge-base/config/platforms.json` as a repo-root sibling —
which means the service deploys the **whole repo** (not just `frontend/`).

## How to (re)deploy — `scripts/deploy-frontend.sh`

The deploy is committed as **`scripts/deploy-frontend.sh`** (run with bash, from anywhere):

```
scripts/deploy-frontend.sh ["deploy message"]
```

Why a script and not a `frontend/railway.json`: the frontend and backend share one monorepo and
deploy from the same repo root, but the repo-root `railway.json`, `Dockerfile` and `.dockerignore`
are **backend-only** (Dockerfile builder, `/health`, and a dockerignore that strips `frontend/` out
of the build context). Railway's config-as-code **overrides** per-service settings, and the
per-service config path is deprecated — so a plain `railway up` for `obi-web` would rebuild the
**backend** image and fail. The script's fix: move those three backend-only files aside for the
upload only, run `railway up --service obi-web`, and restore them immediately via an EXIT trap (even
on error). `obi-web` then builds with **Railpack** via its own service settings: build
`pnpm --filter web build`, start `pnpm --filter web start`. The backend is never modified or
redeployed.

`OBI_ORIGIN` is baked into `/obi.js` at **build** time. If the frontend's public URL ever changes,
set the `OBI_ORIGIN` service variable on `obi-web` **first**, then run the script.

> This deploy is **owner-gated** (it ships outward-facing code to a live service). The agent does not
> run it unprompted. After it runs, verify with `node frontend/scripts/embed-check-live.mjs` and save
> the output in the PR.

## What a correct deploy does (for reference)

Build (pnpm workspace, from the repo): `pnpm install` (resolves `@omniboost/contracts` +
`@omniboost/design-tokens`), then `pnpm --filter web build` → `build:obi` (esbuild bundles
`src/features/embed/loader.ts` to `public/obi.js`, injecting `OBI_ORIGIN`) then `next build`; start
`pnpm --filter web start` (`PORT` set by Railway).

Required service variables:
- `AUTOMATION_API_BASE_URL` = the backend Railway URL (`https://obi-backend-production.up.railway.app`).
- `CHAT_API_KEY` = the backend's `CHAT_API_KEY` (fail-closed: the proxy 503s if unset).
- `APP_ENV=production` (gates the `/embed` CSP to non-dev behavior).
- `OBI_ORIGIN` = the deployed origin, present **at build time** (baked by esbuild).
- `OBI_INTERNAL_ORIGIN` = a loopback (e.g. `http://127.0.0.1:${PORT}`) so the Edge middleware's
  internal active-domains fetch does not loop back through the public host and 403 the frame.

Must-be-true after deploy (re-run `frontend/scripts/embed-check-live.mjs`):
- `/obi.js` + `/embed` served from the stable origin.
- `/obi.js` has the deployed origin baked (not the host-page fallback).
- `/embed` `frame-ancestors` equals the active `platforms.json` domains.
- The service is healthy in eu-west.

## Who can embed (and the external-domain caveat)

`/embed`'s `frame-ancestors` lists only the domains of **active** `platforms.json` entries. The
embedding partners are **Base** (Marien) and **Data Hub** (Jasper); Mews, Toast and Opera Cloud are
source/target systems inside a token, never platforms. Today `platforms.json` holds three entries:

- `obi-test` — **active, temporary** (Supabase Auth issuer). Its domains are
  `obi-web-production.up.railway.app`, `base.development.omniboost.io`, `app.omniboost.io` and
  `datahub.omniboost.io`. Remove it once a real partner entry is live.
- `base` — inactive (issuer `https://base.development.omniboost.io`).
- `datahub` — inactive (issuer and JWKS still TODO).

A domain becomes embeddable only when it is on an active entry and the backend + frontend redeploy.
The partner integration guide is
`docs/Final_docs/1-how-partners-integrate-with-obi/how-partners-integrate-with-obi.md`.

## Known caveats carried from the 8.4.3 deploy (see the ledger entry)

- **No authenticated chat in production yet.** The launcher and iframe render, but the widget cannot
  obtain a trusted token without the Phase 4.x platform integration (issuer + public JWKS + a
  per-platform token endpoint); the test-host signing keys are local-only. Full end-to-end chat is a
  local or post-integration test.
- **Custom domain deferred.** The origin is the Railway host, not `obi.omniboost.com` (needs owner
  DNS). See decision `obi-js-url` in `docs/plan/decisions.md`.
- **`CHAT_API_KEY` rotation recommended (owner).** During the deploy it was printed to a session
  transcript via `railway variable list --kv`; it is stored as a Railway reference (not a copy), so
  the wiring is safe, but rotation is advised. Avoid `railway variable list --kv/--json` on
  secret-bearing services.

## Optional improvement (not required by 8.4.3)

Add a dedicated `/health` route to the frontend and set the service `healthcheckPath` to it (the
backend uses `/health`). Today the service healthcheck uses the default and the root `/` returns 200,
which satisfies "the service is healthy." Deferred to avoid churn on a working deploy.
