# Brief · How to add a host platform

**Audience:** an Obi maintainer (us). Part config-only (we do it now), part blocked on the external platform's developers (their real values).

A **host platform** is a partner site that embeds the Obi widget and mints JWTs for its users. Today there are exactly two partners: **Base** (Marien, entry `base`) and **Data Hub** (Jasper, entry `datahub`), both `active: false` until their issuer and JWKS are live. `obi-test` is a temporary active entry (Supabase Auth issuer) that lets the backend boot in production and lets the partner hosts embed a chat not narrowed to a connection (all indexed pages) until their own entry goes active. **Mews, Toast and Opera Cloud are not platforms** — they are source/target *systems* in `knowledge-base/config/product_catalog.json`, carried inside a partner's token as `source_system` / `target_system`. Each platform is one entry in the registry: an issuer, a JWKS URL, allowed browser domains, a token lifetime, allowed algorithms, an active flag, and the `allowed_integrations` (the systems it may name as source). Adding one is a **data-driven config change** — no Python or TypeScript.

The partner-facing guide (what the partner builds and sends back) is [how partners integrate with Obi](../1-how-partners-integrate-with-obi/how-partners-integrate-with-obi.md).

The trust boundary, end to end:

```
platforms.json (registry)
  → platforms.py        load + validate + trust-guard active entries
  → token_verifier.py   verify the JWT (iss→entry, alg, JWKS by kid, aud=obi, exp/iat, lifetime, business claims)
  → auth_context.py     active-gate (AUTH-1) + source vend gate (CIP-A1) + source enablement → AuthContext
frontend reads the SAME file → CSP frame-ancestors + postMessage origin allow-list
```

> The host key is **not** per-platform. `CHAT_API_KEY` is a single global shared secret authenticating the trusted web proxy → backend leg. Adding a platform does **not** require a new host key. Per-platform trust rides entirely on the JWT.

---

## Two buckets: what we can do now vs. what needs the platform's devs

### Bucket A — config-only, do it now (add the entry inactive, or wire the local test)
You can create the whole entry immediately as **`active: false`**. An inactive entry: is skipped by CSP and the frontend loader, still verifies a token if one arrives, but is **denied any chat** at the gate. That lets us stage the config and test locally with throwaway keys before the platform gives us anything.

### Bucket B — needs the external platform's real values (before `active: true` in production)
Four values must come from the platform's developers:

| Value | What it is |
|---|---|
| `issuer` | the exact `iss` string they sign with — real `https://` host, no `TODO`/`PLACEHOLDER`, not loopback, not `.local` |
| `jwks_url` | real `https://` URL serving their public JWKS (fetched by `kid`, cached) |
| `domains` | the real browser host(s) where the widget runs — feeds CSP `frame-ancestors` + the bridge origin allow-list |
| `allowed_integrations` | the systems you trust them to name as `source_system` (owner decision; each must be a key of the `integrations` map) |

We control the rest: `lifetime_minutes` (≤1440), `algs` (subset of `RS256`/`ES256`), `active`, and the `allowed_integrations` trust call.

---

## The entry shape

`knowledge-base/config/platforms.json` → `platforms` map. The committed `base` entry is the real example:
```json
"base": {
  "issuer": "https://base.development.omniboost.io",
  "jwks_url": "https://base.development.omniboost.io/obi/jwks",
  "domains": ["base.development.omniboost.io", "app.omniboost.io"],
  "lifetime_minutes": 60,
  "algs": ["RS256"],
  "active": false,
  "allowed_integrations": ["mews", "toast", "opera-cloud"]
}
```
`datahub` is the other partner entry: domain `datahub.omniboost.io`, issuer and JWKS still `TODO` placeholders, `active: false`. Inactive entries are exactly why a production boot never trusts a placeholder: the trust guard only runs on active entries, and an inactive one serves no chat.

The token a partner mints carries the directed connection: `source_system`, `target_system` and `business_id` (plus `iss`, `aud=obi`, `sub`, `iat`, `exp`). Only the **source** decides whether Obi shows (`ADR-source-system-decides-widget-eligibility`): it must resolve in the product catalog, be in the issuer's `allowed_integrations` (else 401), and be in the catalog's `enabled_sources` (`mews`, `toast`, `opera-cloud`; else 403 with reason `source_not_enabled`). The target is never checked; it only picks routing labels, and an unknown target falls back to `obi-general` + `{source}-general`.

---

## Steps

### 1. Confirm the systems exist
Every value you put in `allowed_integrations` must be a key of the `integrations` map in `platforms.json` (its value lists are empty — the old knowledge-scope mapping is retired by `ADR-routing-labels-sole-content-axis`), and the system must exist in `knowledge-base/config/product_catalog.json`. `mews` / `toast` / `opera-cloud` already exist. A brand-new system is its own runbook first — see [`add-an-integration.md`](./add-an-integration.md).

### 2. Add the platform entry (inactive)
Add a block like the one above under a new key. Keep `active: false` until Bucket B is satisfied. Pick `allowed_integrations` deliberately: it is the set of source systems this partner may vend, and it is an owner trust decision (both partner entries list `["mews", "toast", "opera-cloud"]`, marked decision-needed in the file's `_readme`). If the partner's host should embed a chat not narrowed to a connection before its own entry is active, its domain can ride on `obi-test`'s `domains` until then; drop it from `obi-test` when the partner entry goes active.

### 3. Prove it locally with throwaway keys
Follow [`localhost-test.md`](./localhost-test.md) — generate RS256 test keys, point both apps at `platforms.local.json` via `PLATFORMS_PATH`, and verify a routed answer plus the source gate on `localhost`. No committed config needed; the `test-*` entries already exist.

### 4. Write the gating test
See the test section below. Prove the entry loads, its `allowed_integrations` is right, and the active-gate, the vend gate and the source-enablement gate behave.

### 5. (Bucket B) fill the real values and flip `active: true`
Once the platform's devs return the four values, put them in the entry and set `active: true`. In production (`offline = False`) the entry loads **only if it passes the trust guard** (`_reject_untrusted_active_platform`): real `https`, non-placeholder, non-loopback, non-`.local` on both `issuer` and `jwks_url`, and real (non-loopback/`.local`) `domains`. No code change, no logic redeploy — the registry is data-driven and re-validated at boot. CSP `frame-ancestors` and the postMessage allow-list update automatically from the now-active domains.

### 6. Hand-over for the partner's devs
The partner's developers need to know what to build and what to send back:
- [How partners integrate with Obi](../1-how-partners-integrate-with-obi/how-partners-integrate-with-obi.md) — the one guide for both partners.
- `docs/embedding/base.md` and `docs/embedding/datahub.md` — the per-partner packs.

---

## Where the code enforces all this (links)

| Concern | Location |
|---|---|
| Registry entry + loader + startup validation | `backend/app/platform/config/platforms.py` → `PlatformEntry`, `load_platform_registry` |
| Trust guard (rejects untrusted active entries) | `platforms.py` → `_reject_untrusted_active_platform` (+ `_is_loopback_host`, `_is_dot_local_host`) |
| Offline vs. production decision | `backend/app/platform/config/settings.py` → `_OFFLINE_ENVS`, `is_offline_env`, `platform_registry` |
| JWT verification | `backend/app/features/rag_agent/server/token_verifier.py` → `TokenVerifier.verify` |
| Active-gate (AUTH-1) + source vend gate (CIP-A1) + source enablement | `backend/app/features/rag_agent/application/auth_context.py` → `build_auth_context`, `_build_directed_context` |
| Systems, `enabled_sources`, routing labels | `backend/app/platform/config/product_catalog.py` |
| Host key (global) | `backend/app/features/rag_agent/server/router.py` → `_verify_api_key` |
| Active embedder domains (server) | `frontend/src/features/embed/platforms.ts` → `activeDomains` |
| CSP + postMessage origin allow-list | `frontend/src/features/embed/csp.ts` → `effectiveEmbedderDomains`, `toEmbedderOrigins`, `computeEmbedCsp` |
| Embed page wiring | `frontend/src/app/embed/page.tsx`; bridge `frontend/src/features/embed/iframe-bridge.ts` → `initIframeBridge` |

---

## Tests that already protect this, and where a new one goes

- **Loader / trust guard** — `backend/app/platform/config/tests/test_platforms.py` (trust-guard suite: placeholder/non-https/loopback/`.local` refused outside offline; `datahub` pinned set; local-file lockstep).
- **Active-gate + vend gate** — `backend/app/features/rag_agent/tests/test_auth_context.py`.
- **Directed gate (source decides, target never checked)** — `backend/app/features/rag_agent/tests/test_mi_gate_directed.py`, `backend/app/features/rag_agent/tests/test_mi_gate_visibility.py`.
- **JWT verify** — `backend/app/features/rag_agent/tests/test_token_verifier.py`.
- **Fail-closed prod / settings** — `backend/app/platform/config/tests/test_settings.py`.
- **End-to-end 401/scoping through `/chat`** — `backend/app/features/confluence_sync/tests/test_router_auth_context.py`.
- **Frontend CSP** — `frontend/src/features/embed/tests/frame-csp.test.ts`.

**A new host platform's proof belongs in:** a registry-load assertion in `test_platforms.py` (mirror `test_platforms_real_file_datahub_vends_product_integrations`); active-gate + vend behaviour in `test_auth_context.py`; and an end-to-end 401/scoping case in `test_router_auth_context.py`. Name each `test_<stage>_<behavior>` and name the design panel it protects.

---

## Pitfalls

- **`active: true` in production fails closed** unless issuer + jwks + domains are real `https`, non-placeholder, non-loopback, non-`.local`. This is why `datahub` stays `active: false` while its issuer/JWKS are `TODO` — flipping it would stop a production boot, by design.
- **No new host key** and **no issuer↔host-key wiring** — `CHAT_API_KEY` is global. If you went looking for a per-platform key, there isn't one; that mandate line does not map to this architecture (documented in the embed-security-final-report).
- **`platforms.local.json` and `frontend/src/app/api/test-hosts/config.ts` must stay in lockstep** for the local flow (asserted by `test_platforms_local_file_allowed_integrations_match_test_hosts`).
- **Inactive is safe to commit** — an `active: false` entry with real values is verified-but-denied and skipped by CSP/loader; use it to stage before go-live.
