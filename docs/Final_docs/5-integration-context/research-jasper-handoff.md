# Research · the Jasper embed handoff — obi.js verification + draft reply — 2026-10-05

> **Status: research notes + a draft for the owner to edit.** Produced by a read-only
> verification pass (owner-ordered parallel batch, 2026-10-05) for the §D.9 Jasper handoff
> item ("verify the actual deployed `obi.js` URL and include it in the reply prepared for
> Jasper"). Nothing here changed code or Confluence. **The reply must not be sent until the
> blocker below is cleared and the owner edits the draft.**

## 1. Finding of record: there is no deployed `obi.js` URL

- The loader (`frontend/src/features/embed/loader.ts` — `window.Obi`: `init`/`clear`/`destroy`)
  is bundled by esbuild to the Next.js static asset **`frontend/public/obi.js`**
  (`frontend/package.json` `build:obi`, `OBI_ORIGIN` baked in at build time; unset → falls back
  to the host page's own origin, which is why same-origin local dev works). Served at
  **`/obi.js`** on whatever host runs the frontend; the iframe points at `${OBI_ORIGIN}/embed`
  (`loader.ts:174`, route `frontend/src/app/embed/page.tsx`).
- **The frontend is not deployed anywhere public.** `railway.json` + the root Dockerfile are
  backend-only; no vercel/netlify config exists; `frontend/CLAUDE.md` says "stays local for
  now"; the only public exposure is the cloudflared quick tunnel with a fresh random hostname
  per run (`scripts/tunnel-embed-test.sh`, self-only). No `OBI_ORIGIN` is configured anywhere.
- The intended production URL in the brief, `https://obi.omniboost.com/obi.js`
  (obi-system-brief.md:1060, :1214), was probed read-only: **HTTP 404 from an Apache parking
  host with a mismatched TLS cert** — not a Next.js deploy.
- **Consequence:** the Jasper reply cannot contain a working URL yet. Prerequisite = a frontend
  deploy (stable origin serving `/obi.js` + `/embed`, `OBI_ORIGIN` baked into the build).
- **DECIDED (owner decision round 2, 2026-10-05, "whatever is easier" delegated):** deploy on
  **Railway**, next to the backend — the CLI is already linked and authenticated, the env-var
  and deploy conventions exist, the service lands in the same eu-west region, and one platform
  means one billing/ops surface; Vercel would add a second account and toolchain for no gain.
  The deploy itself is a later substep (not ordered yet).
- **ORDERING (same decision round):** everything is fixed and human-validated (Phase A) **before**
  any integration into Base/Data Hub — so sending the Jasper reply and collecting the O7
  platform facts are deliberately the **last** Step-5 items, after Phase A.

## 2. The embed contract (what the reply can already state)

```html
<script src="https://<obi-host>/obi.js"></script>
<script>
  Obi.init({ tokenUrl: "/your/obi-token-endpoint" });
</script>
```

`tokenUrl` is the **only** init option (`loader.ts:22–27`): a same-origin endpoint on the
platform's own server that mints the short-lived platform-signed JWT (fetched with
`credentials:"same-origin"`, so the platform session cookie rides; no CORS). Scope/integration
are **never** in the snippet — they travel inside the JWT claims. `Obi.clear()` on logout,
`Obi.destroy()` to unmount.

## 3. Token verification today, and what each side provides

Verification order (`backend/app/features/rag_agent/server/token_verifier.py:78–130`): `iss` →
registry entry; `alg` allow-list (never HS256); key by `kid` via the entry's `jwks_url`
(PyJWKClient, 5 s timeout, cached); signature + `exp`/`iat`/`iss`/`aud:"obi"`/`sub`; lifetime
≤ the platform's `lifetime_minutes`; business claims `company_id`/`company_name`/`integration`
all-three-or-none. Then `build_auth_context`
(`rag_agent/application/auth_context.py:104–138`): platform active, integration known and in
the issuer's `allowed_integrations` — each failure a 401.

- **Jasper provides:** (a) an issuer string; (b) a reachable JWKS URL (RS256/ES256 keys by
  `kid`); (c) the embed domains; (d) the integration values the hub vends; (e) the
  token-minting endpoint signing the claims above.
- **We do:** add his entry to `knowledge-base/config/platforms.json` (today `datahub` is
  `TODO`/`active:false`; the only active issuer is the temporary `obi-test`), map
  integration→scopes, flip `active:true`, redeploy the backend AND rebuild/redeploy `obi.js` +
  the frame (the frame's `frame-ancestors` CSP derives from active `domains`).
- **"Staging JWKS" caveat:** no staging environment exists at all. Either Jasper stands up a
  staging JWKS endpoint (still needs our frontend deployed to embed on), or the local
  test-host harness (`frontend/src/app/api/test-hosts/…` — mints real JWTs, serves JWKS at
  `/.well-known/<issuer>/obi-jwks.json`, local-only) is the stand-in. Owner picks.

## 4. The four test-matrix rows (today's contract = one `integration` claim)

| Case | Status today |
|---|---|
| Single integration | **Works today** — one `integration` claim → `scopes_for` → `allowed_scopes` |
| Multiple integrations | **Requires future implementation** — the three-slot contract (§D.1/§D.13) is designed, not built; today's claim is a single string |
| Unsupported integration | **Works today** as a 401 (unknown → `UnknownIntegrationError`; not vendable by the issuer → `IntegrationNotAllowedError`) |
| Revoked scope | **Works today** as a denial via registry edit (`active:false` → 401, or drop the mapping) + backend redeploy; effective within the token's ≤60-min lifetime — **no instant per-token revocation** |

## 5. Draft reply skeleton (owner to edit; do not send as-is)

> **Subject: Obi widget embed — what we need from you, and one blocker on our side**
>
> Hi Jasper,
>
> **The embed contract.** One script tag plus one init call on your page (snippet above).
> `obi.js` draws the launcher, opens the chat iframe from our domain, fetches a signed JWT
> from your `tokenUrl` at click, renews it before expiry, and forgets it on `Obi.clear()`.
>
> **Blocker on our side (honest status).** The Obi frontend is not deployed publicly yet —
> only the backend is live. I can't hand you a stable `obi.js` URL until the frontend deploy
> lands; I'll confirm the exact URL the moment it's up. *[Owner: target host + ETA.]*
>
> **What we need from you:** issuer string · JWKS endpoint URL · embed domain(s) · the
> integration value(s) you'll assert · a token-minting endpoint (`iss`, `aud:"obi"`, `sub`,
> `iat`, `exp` ≤ 60 min, and `company_id`+`company_name`+`integration` all three or none).
>
> **Planned embed test, four cases:** single integration (works today) · multiple
> integrations (future — the 3-slot contract is designed, not built) · unsupported
> integration (works today, 401) · revoked scope (works today via registry change, effective
> within the token lifetime).
>
> *[Owner: pick the staging-JWKS option — your endpoint vs our local harness.]*
