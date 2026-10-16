# Partner facts & activation status — Base (Marien) / Data Hub (Jasper)

> **Purpose.** The single place that records, per partner, which of the five integration facts are
> **confirmed** and which are still **missing**, plus the ready-to-paste `platforms.json` entry for
> each. Nothing here activates a registration. Every entry stays `active: false` until its issuer,
> JWKS and token endpoint are verified against a fresh signed token (the sequence in
> `phase-9-partner-replies.md` §"What happens after they reply"). Facts are **owner/partner-supplied,
> never invented** (never-bend rule 12).
>
> Opened 2026-10-13 (owner decision round 4, `plan.md` §D.18). Advances open item **O7**
> (`decision-memo.md` §5) and the `ov-auth-key` tracking row (`docs/plan/decisions.md`). This doc is
> the request/status ledger; the contract both partners receive is `phase-9-partner-replies.md`.

## The five facts we need, per partner

Each is read directly into one `platforms.json` field or into the directed token the partner's
endpoint mints (schema: `packages/contracts/src/token-claims.json`; registry dataclass
`backend/app/platform/config/platforms.py:91-107`):

| # | Fact | Where it lands | Constraint |
|---|---|---|---|
| 1 | Issuer string (`iss`) | `platforms.json` `issuer` (the registry is keyed by it) | one per platform; https; not a `.local`/loopback/placeholder when active |
| 2 | JWKS URL | `platforms.json` `jwks_url` | reachable https; keyed by `kid`; **RS256 or ES256** (HS\* is rejected at load) |
| 3 | Embed domain(s) | `platforms.json` `domains` (bare `host[:port]`, no scheme) | feeds the `/embed` `frame-ancestors` CSP; a missing origin blocks the embed |
| 4 | Source/target ids the hub vends | `platforms.json` `allowed_integrations` (vend set) + the token's `source_system`/`target_system` | canonical catalog ids (`product_catalog.json`); every vend id must be a key of the `integrations` map |
| 5 | Token-minting endpoint (`tokenUrl`) | partner-side; not stored by us | signs the directed JWT; same origin as the embedding page |

Token the endpoint must mint (directed form, current per ADR-0020): `iss`, `aud:"obi"`, `sub`,
`iat`, `exp` (≤ the platform's `lifetime_minutes`, 60 by default), plus `business_id` +
`source_system` + `target_system`. Verified in `token_verifier.py:146-217`; the gate builds the
routing identity in `auth_context.py:173-230`.

---

## Base — Marien

**Status: not activatable. 0 of 5 facts confirmed.** Earlier embed hostnames seen but unconfirmed
for this integration; everything else outstanding.

| Fact | State | What we have | What we still need |
|---|---|---|---|
| 1 · Issuer | **MISSING** | — | the exact `iss` string Base's tokens will carry. A hostname is not an issuer. |
| 2 · JWKS URL | **MISSING** | — | a reachable https JWKS URL (RS256/ES256), keyed by `kid`. |
| 3 · Embed domains | **unconfirmed** | earlier: `app.omniboost.io` (live), `base.development.omniboost.io` (dev) | reconfirm the exact HTTPS origins where Obi will actually appear for this integration. |
| 4 · Source/target ids | **MISSING** | we asked for separate source + target + category | the canonical source id and target id per customer, and one complete example payload. |
| 5 · Token endpoint | **MISSING** | `/obi/token` was our suggested path; Marien discussed implementing it | the confirmed deployed endpoint URL. |

**Special requirement — multi-customer context switch (Marien, confirmed).** One Base user can reach
multiple customers and integrations, and the selected customer/connection can change **without
logging out**. This is **supported in the widget today** — it is a documentation and test gap, not a
build gap:

- The iframe bridge decodes each token's scope (`iframe-bridge.ts:81-106`) from `source_system`,
  `target_system` and `company_id`/`business_id`. When the host posts a replacement `obi:token`
  whose scope differs, it fires `onScopeChange` → `restart()`, which aborts the in-flight stream,
  clears the conversation and empties the thread (`embed-frame.tsx:55-61`,
  `chat-session-provider.tsx:190-196`). A **`business_id` change (customer switch) is a scope
  change**, so it resets the chat — no answer carries across customers.
- Equivalently the host can re-call `Obi.init({ tokenUrl })`, which is idempotent and spins a fresh
  iframe = fresh chat (`loader.ts:248-258`).
- The backend re-verifies every token and keys the chat-session row on `(sha256(sub), company_id)`;
  a switch replaces labels + block in place. Company isolation holds per token.

So the **agreed approach for Base**: on a customer/connection switch, Base re-fetches (or re-mints)
the token for the newly-selected customer with the new `business_id` (+ the new `source`/`target`)
and either re-points `Obi.init` or posts the new `obi:token`; Obi resets the chat on the scope change.
What we still need to agree with Marien: the **trigger** on their side (which UI event re-fetches the
token) and whether they prefer re-init or token-replacement. See Phase A Case 17 for the validation.

---

## Data Hub — Jasper

**Status: not activatable. 0 of 5 facts confirmed** (a local fixture exists, but a local test issuer
and an expired, locally-signed token establish nothing about staging).

| Fact | State | What we have | What we still need |
|---|---|---|---|
| 1 · Issuer | **MISSING** | local example `https://pos-pms-laravel.test` (fixture only) | the real staging `iss`. |
| 2 · JWKS URL | **MISSING** | inline public JWKS with `kid: datahub-local-1`; proposed `https://<staging-domain>/.well-known/jwks.json` | the deployed staging JWKS URL. |
| 3 · Embed domains | **MISSING** | `https://www.datahub.be` appeared in our own example — not confirmed as a staging origin | the exact HTTPS staging origin(s) Obi will load on. |
| 4 · Source/target ids | **MISSING, do not infer** | sample carried legacy `integration: toast-opera`; Jasper confirmed separate source/target/category is possible | an explicit directed example: canonical **source** id → **target** id + category, per customer. **Do not** auto-map `toast-opera` — have Jasper confirm the direction and both canonical ids. |
| 5 · Token endpoint | **MISSING** | `/obi/token` example only | the confirmed deployed staging endpoint URL. |

**Sample facts from Jasper's token (treat as a historical fixture, not a working integration):**
`alg: RS256`, `aud: obi`, user id `30`, customer id `8`, customer name `"Dev Testing locations"`,
token lifetime `600 s`. The customer id (`8`) is suitable as `business_id`/`company_id`. The sample
is **expired** and signed with a **local** issuer/key — decoding it does not prove staging auth works.
**Keep expiry validation on** for the real integration and request a **fresh** token when staging is
ready.

**On `toast-opera`:** this compound is refused by the live gate — `legacy_aliases` is `{}`
(`product_catalog.json:15`), so the catalog resolver returns nothing and the gate 400/401s before any
search (`auth_context.py:202-207`). It is two ids mashed together, not a system. Jasper must send
`toast` and the PMS/accounting target as **two separate canonical ids** with an explicit direction.

---

## Our-side preparation (ready to execute when facts arrive — nothing active yet)

Neither entry is written to `knowledge-base/config/platforms.json` yet, because a registry entry
needs at minimum a real `issuer` and `jwks_url`, and neither partner has confirmed those. The current
file keeps the inactive `datahub` placeholder (`issuer`/`jwks_url` = `"TODO until 4.x"`, `active:
false`) and has **no Base entry**. When the facts land, paste the matching block below and run the
activation sequence (`phase-9-partner-replies.md` §"What happens after they reply").

**Data Hub (update the existing `datahub` placeholder):**

```jsonc
"datahub": {
  "issuer": "<Jasper: staging iss>",
  "jwks_url": "<Jasper: https staging JWKS URL>",
  "domains": ["<Jasper: staging embed host, no scheme>"],
  "lifetime_minutes": 60,          // sample used 600 s — within 60 min, fine
  "algs": ["RS256"],               // sample is RS256; add "ES256" only if they sign with it
  "active": false,                 // flip true only after JWKS + token endpoint + vend rights verify
  "allowed_integrations": ["toast", "mews", "opera-cloud"]  // the vend set — confirm the real source/target ids per customer
}
```

**Base (new entry — add once Marien confirms issuer + JWKS):**

```jsonc
"base": {
  "issuer": "<Marien: iss>",
  "jwks_url": "<Marien: https JWKS URL>",
  "domains": ["app.omniboost.io", "base.development.omniboost.io"],  // RECONFIRM the exact origins
  "lifetime_minutes": 60,
  "algs": ["RS256", "ES256"],      // confirm which they sign with
  "active": false,
  "allowed_integrations": []       // set to the canonical source/target ids Base vends, per customer
}
```

**Two prep notes:**

1. **Accounting targets need a map key.** `allowed_integrations` values must be keys of the
   top-level `integrations` map (today: `mews`, `toast`, `opera-cloud` — `platforms.json:10-14`).
   If a hub vends an **accounting** target (`quickbooks-online` / `xero`, both already in
   `product_catalog.json`), that id must be added to the `integrations` map too, or the registry
   fails to load. Add it in the same change that activates the partner.
2. **Embed origins flow automatically.** Adding a confirmed origin to an **active** entry's `domains`
   propagates to both the `/embed` `frame-ancestors` CSP (middleware → `activeDomains()` →
   `computeEmbedCsp`, `frontend/src/middleware.ts:51-56`) and the backend's `active_domains()`. On an
   inactive entry the domains are inert.

## obi.js asset URL (confirmed, for both partners)

The embed `<script src>` is the **web** host: `https://obi-web-production.up.railway.app/obi.js`
(Railway service `obi-web`; confirmed by `frontend/scripts/embed-check-live.mjs:38` and decision
`obi-js-url`, `decisions.md:20`). The **backend** host
(`obi-backend-production.up.railway.app`) is the chat API the frame talks to server-to-server — **not**
the script source. `obi.js` moves to a branded `obi.omniboost.com` before go-live; the only change on
a partner's side is that one `src` line, with advance notice.

## Local-harness verification (Option B — runs now, in parallel)

While partner staging is prepared, we verify our own implementation with the local test-host harness
(`frontend/src/app/test-hosts/*`, `frontend/src/app/api/test-hosts/*`), which mints RS256 directed
tokens against `test-*.local` issuers registered in `platforms.local.json`. The
`/test-hosts/connection-switch` page already drives a source/target switch to prove the thread resets.
**Local-harness passes and partner-staging passes are recorded separately** (Phase A integration
cases): passing our local tests does not establish that a partner's integration works.
