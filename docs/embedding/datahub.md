# Obi embed — Data Hub

**Who:** the Data Hub, integration owned by **Jasper**. The Data Hub is one of the two partners
that embed Obi (the other is Base, see [`base.md`](base.md)). Mews, Toast and Opera Cloud are
systems a Data Hub customer connects, not platforms that embed Obi.

- **How a partner integrates** (script tag, token endpoint, claims, JWKS):
  [`how-partners-integrate-with-obi.md`](../Final_docs/1-how-partners-integrate-with-obi/how-partners-integrate-with-obi.md)
- **Which facts we have from the Data Hub and which are missing:**
  [`partner-facts.md`](../Final_docs/5-integration-context/partner-facts.md) (§ Data Hub — Jasper)

## Status (2026-10-20)

- `knowledge-base/config/platforms.json` has a `datahub` entry, **`active: false`**. Its issuer and
  JWKS URL are still `TODO` placeholders; its domain is `datahub.omniboost.io`.
- One of the five facts is in (the embed domain, from the owner). Still missing from Jasper: the
  staging issuer, the deployed JWKS URL, an explicit directed source → target example per
  customer, and the deployed token endpoint.
- The sample token Jasper shared is expired and signed by a local issuer; it is a fixture, not
  proof that staging auth works. Its legacy `integration: toast-opera` value is not to be
  auto-mapped to a direction.

## What is live today

`datahub.omniboost.io` is on the `/embed` frame CSP through the temporary `obi-test` platform, so
the widget can load there and answer **general-only** questions. No Data Hub-signed token is
honoured until the `datahub` entry has real values and goes active.

## What the Data Hub will send

The directed token: `iss`, `aud: "obi"`, `sub`, `iat`, `exp` (at most 60 minutes), `source_system`,
`target_system`, `business_id`. Per
[ADR-source-system-decides-widget-eligibility](../adr/source-system-decides-widget-eligibility.md),
only the **source** decides whether Obi shows: a supported source (Mews, Toast, Opera Cloud) shows
Obi for any target; an unknown or unsupported source hides it.
