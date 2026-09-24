# Brief · How to add a host platform

**Audience:** an Obi maintainer (us). Part config-only (we do it now), part blocked on the external platform's developers (their real values).

A **host platform** is a place that embeds the Obi widget and mints JWTs for its users — e.g. `datahub`, the inactive `mews` / `toast` / `opera-cloud`, and a future `base`. Each is one entry in the platform registry: an issuer, a JWKS URL, allowed browser domains, a token lifetime, allowed algorithms, an active flag, and the `allowed_integrations` it may assert. Adding one is a **data-driven config change** — no Python or TypeScript.

The trust boundary, end to end:

```
platforms.json (registry)
  → platforms.py        load + validate + trust-guard active entries
  → token_verifier.py   verify the JWT (iss→entry, alg, JWKS by kid, aud=obi, exp/iat, lifetime, business claims)
  → auth_context.py     active-gate (AUTH-1) + integration allow-list gate (CIP-A1) → AuthContext
frontend reads the SAME file → CSP frame-ancestors + postMessage origin allow-list
```

> The host key is **not** per-platform. `CHAT_API_KEY` is a single global shared secret authenticating the trusted web proxy → backend leg. Adding a platform does **not** require a new host key. Per-platform trust rides entirely on the JWT.

---

## Two buckets: what we can do now vs. what needs the platform's devs

### Bucket A — config-only, do it now (add the entry inactive, or wire the local test)
You can create the whole entry immediately as **`active: false`**. An inactive entry: is skipped by CSP and the frontend loader, still verifies a token if one arrives, but is **denied scoped access** at the gate. That lets us stage the config and test locally with throwaway keys before the platform gives us anything.

### Bucket B — needs the external platform's real values (before `active: true` in production)
Four values must come from the platform's developers:

| Value | What it is |
|---|---|
| `issuer` | the exact `iss` string they sign with — real `https://` host, no `TODO`/`PLACEHOLDER`, not loopback, not `.local` |
| `jwks_url` | real `https://` URL serving their public JWKS (fetched by `kid`, cached) |
| `domains` | the real browser host(s) where the widget runs — feeds CSP `frame-ancestors` + the bridge origin allow-list |
| `allowed_integrations` | the set of integration claim values you trust them to assert (owner decision) |

We control the rest: `lifetime_minutes` (≤1440), `algs` (subset of `RS256`/`ES256`), `active`, the `allowed_integrations` trust call, and the `integrations → scope` mapping.

---

## The entry shape

`knowledge-base/config/platforms.json` → `platforms` map:
```json
"base": {
  "issuer": "https://<their-host>",
  "jwks_url": "https://<their-host>/.well-known/obi-jwks.json",
  "domains": ["<their-browser-host>"],
  "lifetime_minutes": 60,
  "algs": ["RS256", "ES256"],
  "active": false,
  "allowed_integrations": ["mews", "toast", "opera-cloud"]
}
```
The committed `datahub` entry is the live example (active, but with `TODO` placeholder issuer/jwks — which is exactly why a real production boot fails closed until real values arrive).

---

## Steps

### 1. Confirm the scopes and integration mappings exist
Every value you put in `allowed_integrations` must be a key of the `integrations` map in `platforms.json`, and each of those must map to a scope in `knowledge-base/config/knowledge_scopes.json`. `mews` / `toast` / `opera-cloud` already exist. A brand-new integration is its own runbook first — see [`add-an-integration.md`](./add-an-integration.md).

### 2. Add the platform entry (inactive)
Add the block above under a new key (e.g. `"base"` — not reserved anywhere in code). Keep `active: false` until Bucket B is satisfied. Pick `allowed_integrations` deliberately: a self-serving platform lists only its own (`["mews"]`); a hub (datahub/base) lists the product set it may vend.

### 3. Prove it locally with throwaway keys
Follow [`localhost-test.md`](./localhost-test.md) — generate RS256 test keys, point both apps at `platforms.local.json` via `PLATFORMS_PATH`, and verify a scoped answer + cross-integration isolation on `localhost`. No committed config needed; the `test-*` entries already exist.

### 4. Write the gating test
See the test section below. Prove the entry loads, its `allowed_integrations` is right, and the active-gate + integration allow-list behave.

### 5. (Bucket B) fill the real values and flip `active: true`
Once the platform's devs return the four values, put them in the entry and set `active: true`. In production (`offline = False`) the entry loads **only if it passes the trust guard** (`_reject_untrusted_active_platform`): real `https`, non-placeholder, non-loopback, non-`.local` on both `issuer` and `jwks_url`, and real (non-loopback/`.local`) `domains`. No code change, no logic redeploy — the registry is data-driven and re-validated at boot. CSP `frame-ancestors` and the postMessage allow-list update automatically from the now-active domains.

### 6. Hand-over pack for the platform's devs
The platform's developers need to know what to build and what to send back. That lives in `docs/embedding/`:
- `docs/embedding/datahub.md` — the Data Hub pack (fill 4 values to activate).
- `docs/embedding/base.md` — the Base pack (shows the exact new `"base"` JSON block; Base is not yet a committed entry).
- `docs/embedding/mews.md`, `toast.md`, `opera-cloud.md` — self-serving single-integration packs.

---

## Where the code enforces all this (links)

| Concern | Location |
|---|---|
| Registry entry + loader + startup validation | `backend/app/platform/config/platforms.py` → `PlatformEntry`, `load_platform_registry` |
| Trust guard (rejects untrusted active entries) | `platforms.py` → `_reject_untrusted_active_platform` (+ `_is_loopback_host`, `_is_dot_local_host`) |
| Offline vs. production decision | `backend/app/platform/config/settings.py` → `_OFFLINE_ENVS`, `is_offline_env`, `platform_registry` |
| JWT verification | `backend/app/features/rag_agent/server/token_verifier.py` → `TokenVerifier.verify` |
| Active-gate (AUTH-1) + integration gate (CIP-A1) | `backend/app/features/rag_agent/application/auth_context.py` → `build_auth_context` |
| Host key (global) | `backend/app/features/rag_agent/server/router.py` → `_verify_api_key` |
| Active embedder domains (server) | `frontend/src/features/embed/platforms.ts` → `activeDomains` |
| CSP + postMessage origin allow-list | `frontend/src/features/embed/csp.ts` → `effectiveEmbedderDomains`, `toEmbedderOrigins`, `computeEmbedCsp` |
| Embed page wiring | `frontend/src/app/embed/page.tsx`; bridge `frontend/src/features/embed/iframe-bridge.ts` → `initIframeBridge` |

---

## Tests that already protect this, and where a new one goes

- **Loader / trust guard** — `backend/app/platform/config/tests/test_platforms.py` (trust-guard suite: placeholder/non-https/loopback/`.local` refused outside offline; `datahub` pinned set; local-file lockstep).
- **Active-gate + integration gate** — `backend/app/features/rag_agent/tests/test_auth_context.py`.
- **JWT verify** — `backend/app/features/rag_agent/tests/test_token_verifier.py`.
- **Fail-closed prod / settings** — `backend/app/platform/config/tests/test_settings.py`.
- **End-to-end 401/scoping through `/chat`** — `backend/app/features/confluence_sync/tests/test_router_auth_context.py`.
- **Frontend CSP** — `frontend/src/features/embed/tests/frame-csp.test.ts`.

**A new host platform's proof belongs in:** a registry-load assertion in `test_platforms.py` (mirror `test_platforms_real_file_datahub_vends_product_integrations`); active-gate + allow-list behaviour in `test_auth_context.py`; and an end-to-end 401/scoping case in `test_router_auth_context.py`. Name each `test_<stage>_<behavior>` and name the design panel it protects.

---

## Pitfalls

- **`active: true` in production fails closed** unless issuer + jwks + domains are real `https`, non-placeholder, non-loopback, non-`.local`. This is why placeholder `datahub` cannot boot in prod today — by design.
- **No new host key** and **no issuer↔host-key wiring** — `CHAT_API_KEY` is global. If you went looking for a per-platform key, there isn't one; that mandate line does not map to this architecture (documented in the FINAL-REPORT).
- **`platforms.local.json` and `frontend/src/app/api/test-hosts/config.ts` must stay in lockstep** for the local flow (asserted by `test_platforms_local_file_allowed_integrations_match_test_hosts`).
- **Inactive is safe to commit** — an `active: false` entry with real values is verified-but-denied and skipped by CSP/loader; use it to stage before go-live.
