# Obi embed — Base

**Who:** Base, integration owned by **Marien**. Base is one of the two partners that embed Obi
(the other is the Data Hub, see [`datahub.md`](datahub.md)). Mews, Toast and Opera Cloud are
systems a Base customer connects, not platforms that embed Obi.

- **How a partner integrates** (script tag, token endpoint, claims, JWKS):
  [`how-partners-integrate-with-obi.md`](../Final_docs/1-how-partners-integrate-with-obi/how-partners-integrate-with-obi.md)
- **Which facts we have from Base and which are missing:**
  [`partner-facts.md`](../Final_docs/5-integration-context/partner-facts.md) (§ Base — Marien)

## Status (2026-10-20)

- `knowledge-base/config/platforms.json` has a `base` entry, **`active: false`**: issuer
  `https://base.development.omniboost.io`, JWKS `https://base.development.omniboost.io/obi/jwks`,
  RS256, 60-minute lifetime, domains `base.development.omniboost.io` (dev) and `app.omniboost.io`
  (live).
- The JWKS URL returned **HTTP 500** on 2026-10-20. Base stays inactive until it serves JSON keys;
  activating earlier would make every Base token fail verification.
- The live issuer and JWKS for `app.omniboost.io` are still to come, and so is a deployed token
  endpoint (the one we have is on Marien's local machine).

## What is live today

Both Base hosts are on the `/embed` frame CSP through the temporary `obi-test` platform, so the
widget can load there and answer **general-only** questions. No Base-signed token is honoured
until the `base` entry goes active.

## What Base sends

The directed token: `iss`, `aud: "obi"`, `sub`, `iat`, `exp` (at most 60 minutes), `source_system`,
`target_system`, `business_id`. Base sends display names (e.g. `"PEP PMS"`, `"NetSuite"`); Obi
resolves them case- and space-insensitively. An integer `business_id` is accepted and normalized
to a string.

Per [ADR-source-system-decides-widget-eligibility](../adr/source-system-decides-widget-eligibility.md),
only the **source** decides whether Obi shows: a supported source (Mews, Toast, Opera Cloud) shows
Obi for any target; an unknown or unsupported source hides it.

**Customer switch.** One Base user can switch customer or connection without logging out. Base
re-fetches the token for the new selection and either re-calls `Obi.init` or posts the new token;
Obi resets the chat when the connection changes. The trigger on Base's side is still to be agreed
(see `partner-facts.md`).
