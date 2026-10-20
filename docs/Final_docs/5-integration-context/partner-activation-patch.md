# Partner activation patch — pre-staged, NOT applied

> **Purpose.** A paste-and-go reference so activating a partner in
> `knowledge-base/config/platforms.json` is minutes, not fresh work. For each partner it gives the
> exact JSONC block to paste, filled as far as `partner-facts.md` allows, with the five unknown facts
> marked `"<<BLANK: …>>"`. **Nothing here is applied.** Do **not** paste a block until every blank is
> filled with partner-supplied values — a registry entry with a placeholder `issuer`/`jwks_url` makes
> the backend fail to load (startup validation in `backend/app/platform/config/platforms.py`; facts
> are owner/partner-supplied, never invented — never-bend rule 12).
>
> Created 2026-10-13 (Task 3, `docs/Final_docs/sync-rules/plan.md`). Source of the facts and blanks:
> `partner-facts.md`. Registry shape confirmed against `platforms.json` and `platforms.local.json`;
> accounting-id check confirmed against `product_catalog.json`.
>
> **Update 2026-10-20.** Base's entry is now in `platforms.json` (written 2026-10-16, `active: false`),
> so the Base section below shows that entry instead of a blank block. Since
> ADR-source-system-decides-widget-eligibility only the token's **source** is vend-checked and
> enablement-checked; the target is never checked. Current per-partner state: `partner-facts.md`.

## The five facts (which map into the block, which do not)

| # | Fact | Lands in the JSONC block? | Field |
|---|---|---|---|
| 1 | Issuer (`iss`) | yes | `issuer` (the registry is keyed by it) |
| 2 | JWKS URL | yes | `jwks_url` (reachable https, keyed by `kid`, RS256/ES256) |
| 3 | Embed domain(s) | yes | `domains` (bare `host[:port]`, no scheme) |
| 4 | Source/target vend ids | yes | `allowed_integrations` (every value must be a key of the top-level `integrations` map) |
| 5 | Token-minting endpoint (`tokenUrl`) | **no — partner-side, not stored by us** | used only in the verify sequence below |

Three blanks live inside the Data Hub block (its domain came from the owner; Base's entry is already written); the fifth (the token endpoint) is a partner-side blank the
verify sequence consumes. Which facts each partner has supplied: `partner-facts.md`.

---

## Base — Marien (entry already in `platforms.json`, inactive)

The entry as written on 2026-10-16:

```jsonc
"base": {
  "issuer": "https://base.development.omniboost.io",
  "jwks_url": "https://base.development.omniboost.io/obi/jwks",
  "domains": ["base.development.omniboost.io", "app.omniboost.io"],
  "lifetime_minutes": 60,
  "algs": ["RS256"],
  "active": false,                   // flip true only at step 4 of the verify sequence
  "allowed_integrations": ["mews", "toast", "opera-cloud"]   // owner trust decision (decision-needed)
}
```

Still open before step 4: the JWKS URL returned HTTP 500 (rechecked 2026-10-20) and must serve JSON
`keys`; the deployed token endpoint (the one Marien sent is on his local machine); the live issuer and
JWKS for `app.omniboost.io`.

**Multi-customer context switch (confirmed, supported today).** On a customer/connection switch Base
re-mints the token for the newly-selected customer (new `business_id` + new source/target) and either
re-points `Obi.init({ tokenUrl })` or posts a replacement `obi:token`; Obi resets the chat on the
scope change. Still to agree with Marien: the trigger event and re-init vs. token-replacement. Covered
by Phase A Case 17. No registry field changes for this.

---

## Data Hub — Jasper (UPDATE the existing inactive `datahub` placeholder)

Replace the current `datahub` entry (`issuer`/`jwks_url` = `"TODO until 4.x"`) with:

```jsonc
"datahub": {
  "issuer": "<<BLANK: issuer — Jasper: real staging iss (local fixture https://pos-pms-laravel.test is a fixture only, not staging)>>",
  "jwks_url": "<<BLANK: jwks_url — Jasper: deployed staging JWKS URL (proposed https://<staging-domain>/.well-known/jwks.json; sample kid datahub-local-1)>>",
  "domains": ["datahub.omniboost.io"],   // from the owner 2026-10-16; Jasper to confirm, and whether staging uses another host
  "lifetime_minutes": 60,            // sample used 600 s — within the 60-min cap, fine
  "algs": ["RS256"],                 // sample is RS256; add "ES256" only if they sign with it
  "active": false,                   // flip true only at step 4 of the verify sequence
  "allowed_integrations": ["<<BLANK: allowed_integrations — Jasper: the canonical SOURCE ids the hub vends (only the source is vend-checked); do NOT auto-map toast-opera; every value MUST be a key of the integrations map>>"]
}
```

Fifth blank (partner-side, not in the block):
`<<BLANK: tokenUrl — Jasper: confirmed deployed staging token-minting endpoint URL (/obi/token example only)>>`

**On `toast-opera`:** do not infer. `legacy_aliases` is `{}` in `product_catalog.json`, so a compound
value is refused before any search: as a legacy `integration` claim it is a 400; as `source_system`
it resolves to nothing, so Obi stays hidden (403 `source_not_enabled`). Jasper must send `toast` and the PMS/accounting target
as two separate canonical ids with an explicit direction. Request a **fresh** token when staging is
ready — the sample is expired and locally signed, so decoding it proves nothing about staging auth.
Keep expiry validation on.

---

## (a) Accounting-integrations-map note — REQUIRED before load

`allowed_integrations` values must each be a key of the top-level `integrations` map. Today that map
holds only `mews`, `toast`, `opera-cloud` (`platforms.json` lines 10–14). The accounting ids
`quickbooks-online` and `xero` exist in `product_catalog.json` but are **not** in the `integrations`
map.

Since ADR-source-system-decides-widget-eligibility only the **source** is vend-checked, so an
accounting **target** needs no entry here. **If a hub is ever trusted to vend an accounting source**
(`quickbooks-online` or `xero`; it would also need adding to `enabled_sources`), add that id as a key to the
top-level `integrations` map **in the same change** that activates the partner — otherwise the
registry fails to load at startup (every `allowed_integrations` value must be a key of `integrations`).
The value is an empty list `[]` (the knowledge-scope value lists are retired and empty per ADR-routing-labels-sole-content-axis):

```jsonc
"integrations": {
  "mews": [],
  "toast": [],
  "opera-cloud": [],
  "quickbooks-online": [],   // ADD only if a partner's allowed_integrations vends it
  "xero": []                 // ADD only if a partner's allowed_integrations vends it
}
```

Add only the accounting id(s) a partner actually vends; do not add ids nothing references.

## (b) Verify sequence — run in order, per partner

1. **JWKS reachable.** Confirm the partner's `jwks_url` returns an https JWKS keyed by `kid`, signed
   RS256 or ES256 (HS\* is rejected at load).
2. **Endpoint mints a conforming directed JWT.** The partner's token endpoint mints a fresh token
   carrying `iss`, `aud:"obi"`, `sub`, `iat`, `exp` (≤ `lifetime_minutes`), plus `business_id` +
   `source_system` + `target_system`.
3. **Vend rights.** Every `source_system` the token asserts is in the entry's
   `allowed_integrations` (the target is never checked), and every `allowed_integrations` value is a key of the `integrations` map
   (add accounting ids per note (a) first).
4. **Flip `active:true`.** Set the entry's `active` to `true`.
5. **Redeploy BE + FE.** Redeploy backend and frontend so both pick up the registry change (active
   `domains` then propagate to the `/embed` `frame-ancestors` CSP and the backend's active domains).
6. **Drop the temporary `obi-test` issuer.** Remove the temporary `obi-test` active platform from
   `platforms.json` once a real partner is live.
7. **Run Cases 11–18, partner-staging leg.** Execute the Phase A validation Cases 11–18 against
   partner staging. Local-harness passes do not count as partner-staging passes; they are recorded
   separately.
