# Brief · Recreate the embed test on localhost

**Audience:** an Obi maintainer (us). Goal: run the whole embed flow on your own machine — mint a
JWT, load the widget in a stub host page, get a **scope-isolated** answer — using throwaway RS256
keys and the committed `test-*` platforms. No external platform needed. This is a full rehearsal of
go-live minus the real signing key.

> Port warning up front: the local platform registry pins each test issuer's JWKS at
> **`http://localhost:3100`**. The frontend must run on **:3100** (use `make embed-dev`), not the
> `make web-dev` default of :3000 — otherwise the backend's JWKS fetch 404s and every token 401s.

---

## What already exists on disk (usually zero setup)

- `frontend/.env.local` already holds the four RS256 keypairs (`TEST_OBI_PRIVATE_KEY_*` /
  `TEST_OBI_PUBLIC_KEY_*`), `APP_ENV=local`, `AUTOMATION_API_BASE_URL=http://localhost:8000`,
  `PLATFORMS_PATH=…/knowledge-base/config/platforms.local.json`, and `CHAT_API_KEY`.
- Root `.env` already sets `ENV=local`, the same `PLATFORMS_PATH`, and a byte-identical `CHAT_API_KEY`.
- The committed `knowledge-base/config/platforms.local.json` defines four active test issuers:
  `test-mews` (`integration: mews`), `test-toast` (`toast`), `test-opera` (`opera-cloud`),
  `test-none` (general only).

Only regenerate keys (openssl recipe in `docs/embedding/obi-embed-local-test-keys.md`) if
`frontend/.env.local` was wiped. Note that doc's folder names are stale (`apps/web` / `apps/automation`);
the real roots are `frontend/` and `backend/`, and the registry is at
`knowledge-base/config/platforms.local.json`.

---

## Run it

Two terminals, plus a browser.

```bash
# terminal 1 — backend on :8000 (reads root .env: ENV=local, PLATFORMS_PATH, CHAT_API_KEY)
make api

# terminal 2 — frontend on :3100 (rebuilds public/obi.js first)
make embed-dev

# browser — the purpose-built stub host pages
open http://localhost:3100/test-hosts/toast     # one scoped host
open http://localhost:3100/test-hosts/multi     # switch mews/toast/opera, prove isolation
```

Click the launcher, ask a question, and the answer must be scoped to the active token's integration
(a `toast` token only ever retrieves `obi-toast-test` + `obi-general-test` content, never mews/opera).

**Mint a token by hand** (the app mints on demand; there is no CLI):
```bash
curl http://localhost:3100/api/test-hosts/toast/obi-token   # → {"token":"<RS256 JWT>"}
# names: none | mews | toast | opera-cloud
```

---

## Choose your database — this decides whether you get an answer or a refusal

The embed **auth path** (token → verify → scope) works against any DB. Getting an actual **answer**
needs content in the store for that scope:

- **Path A — live Supabase (turnkey answers).** The root `.env` `DATABASE_URL` points at the live
  Supabase project, which already has the `obi-*-test` scopes seeded from prior Confluence ingestion.
  Just `make api` (no `make up`/`migrate`). A scoped question returns a real cited answer. Use this to
  see the full round trip. (Never run `-m db` tests against this URL — the guard refuses it by design.)
- **Path B — fully local pgvector (isolated, but empty).**
  ```bash
  make up && make migrate        # schema only on :5434 — NO content
  DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5434/omniboost_rag make api
  ```
  A fresh local DB has the schema but **no chunks/vectors**, so a scoped question yields a *refusal*,
  not an answer — which still proves the auth/scope path end to end. For a scoped *answer* offline,
  seed a little curated content: `knowledge-base/seed/seed_curated_knowledge.py` is the only offline
  path that produces a scoped answer without embeddings. (A one-shot `chunk`/vector fixture seeder per
  scope does not exist yet — tracked in `docs/future-ideas.md`.)

---

## What the automated suites already prove (run these to trust the wiring)

```bash
make test-unit                 # backend + kb unit: token verify, scope mapping, CSP, bridge origin
make test-ui                   # Playwright: widget mounts on /test-hosts/none; scope list excludes classified
pnpm --filter web test         # vitest: iframe-bridge, loader, embed-frame, proxy header injection
```

- Backend: `test_token_verifier.py` (RS256, alg allow-list, JWKS by kid, lifetime, business claims),
  `test_auth_context.py` (integration→scope, allow-list gate), `test_chat_endpoint.py` /
  `test_router_auth_context.py` (full `POST /chat` incl. `X-Obi-Token` + 401 paths),
  `test_localhost_embed_config.py` (the committed test-host registry maps each issuer to its scope —
  see below).
- Frontend: `frame-csp.test.ts`, `iframe-bridge.test.ts`, `loader.test.ts`, `embed-frame.test.tsx`,
  `route-handlers.test.ts`.

These prove the auth/scope **plumbing** deterministically with fakes. The one thing they do not do is
click the live launcher and drive a real backend answer — that is the manual browser step above.

---

## The flow, end to end (what happens when you click)

1. Host page runs `Obi.init({ tokenUrl })` → `obi.js` injects the launcher + the `/embed` iframe.
2. On open, the loader fetches `tokenUrl` (`/api/test-hosts/<name>/obi-token`) → RS256 JWT, and
   `postMessage`s it to the frame.
3. The frame bridge (`frontend/src/features/embed/iframe-bridge.ts`) checks
   `event.source === window.parent` and the origin allow-list, then holds the token **in memory only**.
4. Chat send → `POST /api/chat` with `Authorization: Bearer <user-JWT>`. The proxy
   (`frontend/src/features/chat/server/route-handlers.ts`) forwards that JWT to the backend as
   `X-Obi-Token` and injects the global `CHAT_API_KEY` as its own `Authorization` header.
5. Backend `POST /chat` (`backend/app/features/rag_agent/server/router.py`): `_verify_api_key`
   (host key) → `_resolve_auth_context` reads `X-Obi-Token` → `TokenVerifier.verify` (fetches JWKS
   from `http://localhost:3100/...`) → `build_auth_context` maps `integration → allowed_scopes`. That
   scope gates every DB read → an isolated answer.

---

## Gotchas

- **:3100, not :3000** — `make embed-dev` handles this; `make web-dev` does not.
- **`make api` has no counterpart in the old docs** — it's the new backend run target (uvicorn on :8000).
- **Empty local DB → refusals, not a bug** — see Path A vs B.
- **Keep `platforms.local.json` and `frontend/src/app/api/test-hosts/config.ts` in lockstep** — a
  mismatch 401s the local flow (asserted by `test_platforms_local_file_allowed_integrations_match_test_hosts`).
