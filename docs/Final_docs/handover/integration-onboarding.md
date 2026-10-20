# Partner onboarding & offboarding — connecting or disconnecting a partner, end to end

> **Audience:** whoever connects a partner that embeds Obi, or disconnects one.
> **Living doc:** describes the system after `ADR-routing-labels-sole-content-axis` and
> `ADR-source-system-decides-widget-eligibility` (2026-10-20). The partner-facing side is in
> [how partners integrate with Obi](../1-how-partners-integrate-with-obi/how-partners-integrate-with-obi.md).

A **partner** is a site that embeds the Obi widget for its users. There are two: **Base** (Marien,
platform entry `base`) and **Data Hub** (Jasper, platform entry `datahub`), both inactive until their
issuer and JWKS are live. Mews, Toast and Opera Cloud are **systems**, not partners: a partner's
token names one connection between two systems. The partner signs a short token ("the note") for
each user carrying `source_system`, `target_system` and `business_id`; the widget sends it, and the
backend decides from it whether Obi shows and which pages the chat may search.

## Connecting a partner

**1. Register the partner in `knowledge-base/config/platforms.json`** — issuer URL, JWKS location,
browser `domains`, `lifetime_minutes` (1–1440), `algs` (RS256/ES256), `active`, and
`allowed_integrations` (the systems it may name as a source; an owner trust decision). The full
runbook is `../brief/add-a-host-platform.md`. Outside local dev an active issuer must be real HTTPS,
non-placeholder and non-loopback. Production uses `platforms.json`; local testing uses
`platforms.local.json` + the `/test-hosts/*` fake issuers.

**2. Make sure its systems exist** — every system it will send must be in
`knowledge-base/config/product_catalog.json`; a system that may open Obi as a source must also be in
`enabled_sources` (today `mews`, `toast`, `opera-cloud`). A new system is
`../brief/add-an-integration.md`.

**3. Deploy** — commit, redeploy the backend (the platform registry is cached in-process: **a file
edit without restart does nothing**, by design), and redeploy the frontend so the frame CSP and the
loader pick up the active domains.

**4. Partner side** — they embed the widget and mint the note:
```html
<script src="https://obi-web-production.up.railway.app/obi.js"></script>
<script>Obi.init({ tokenUrl: "/their-endpoint/obi-token" });</script>
```
Their token endpoint returns a short-lived RS256 JWT with `iss`, `aud=obi`, `sub`, `iat`, `exp`,
`source_system`, `target_system` and `business_id`, signed by a key whose **public JWKS is served at
the URL registered in step 1** — the backend's TokenVerifier fetches it from there. The local
test-host pages (`frontend/src/app/test-hosts/`, keys in `frontend/.env.local`) are the working
reference implementation. Locally-signed test tokens verify only against a locally-run backend — the
deployed backend can't reach a laptop's JWKS.

**5. Label content** — the pages for each connection carry routing labels (see `tagging-guide.md`).

**6. Verify, in order** — a token whose source is enabled shows the widget and answers a question
only that connection's labelled pages can answer, with a citation · a token whose source is not in
`enabled_sources` hides the widget (`GET /chat/visibility` returns `source_not_enabled`; `POST /chat`
returns 403) · a token from an unknown or inactive issuer is a 401.

## Disconnecting a partner

1. Set the partner `active: false` (or delete its entry) in `platforms.json`; commit + **restart /
   redeploy** — nothing changes until the restart. From then on every one of its tokens is a clean
   **401** on the next request. Tokens are stateless, so there is nothing else to revoke.
2. The partner removes the widget embed from their product (cosmetic — the backend already
   refuses).
3. Content is unaffected: routing labels belong to systems, not partners, so the other partner keeps
   using the same pages.
4. Old `query_trace` rows keep their historical values — they're an audit record, nothing
   re-interprets them.

## Turning a system off as a source

Remove it from `enabled_sources` in `product_catalog.json` and redeploy. Every chat whose source is
that system is hidden (`source_not_enabled`); chats where it is only the target are unaffected, since
the target is never checked.
