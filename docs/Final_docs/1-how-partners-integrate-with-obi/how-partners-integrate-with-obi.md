# How partners integrate with Obi

The single guide to putting Obi inside a partner's product. **Part A** is for the partner and can be
forwarded as is. **Part B** is for us. The visual version is
[how-partners-integrate-with-obi.html](how-partners-integrate-with-obi.html); when the two disagree,
this Markdown file wins.

Last checked against the code: 2026-10-20.

---

## 0. In one minute

A partner page loads Obi's script and gives Obi a short-lived **signed token**. The token names the
customer (`business_id`) and the connection: a **source system** and a **target system**.

- **Only the source system decides whether Obi appears.** If the source is one we support — today
  **Mews, Toast or Opera Cloud** — Obi shows and answers from that connection's documentation. If it
  is not, Obi stays hidden.
- **The target system is never checked.** One source can connect to hundreds of targets, so any
  target is accepted. A target we have no pages for falls back to the source's own pages.
- **No token means no connection.** The widget still works, but Obi does not know the customer's
  systems, so it searches all indexed Omniboost pages instead of the four for one connection (the
  routing labels narrow relevance; they are not an access fence —
  `_resolve_directed_routing` in [`answer_service.py`](../../../backend/app/features/rag_agent/application/answer_service.py)).

The rule is recorded in
[ADR-source-system-decides-widget-eligibility](../../adr/source-system-decides-widget-eligibility.md).

## 1. Status today

| | Base (Marien) | Data Hub (Jasper) |
|---|---|---|
| Embed hosts allowed | `base.development.omniboost.io` (dev), `app.omniboost.io` (live) | `datahub.omniboost.io` |
| What works now | Widget loads; answers without a connection (no token yet) | Widget loads; answers without a connection (no token yet) |
| Registered as a signing partner | Yes, entry `base`, **inactive** | Yes, entry `datahub`, **inactive** |
| Blocking activation | The JWKS URL returns HTTP 500; we need a token from the deployed dev environment | Issuer and JWKS URL not received yet |

Live facts per partner are tracked in
[partner-facts.md](../5-integration-context/partner-facts.md). The partner pages are
[Base](../../embedding/base.md) and [Data Hub](../../embedding/datahub.md).

Live services:

- Obi frontend (the script, the widget frame, the proxy): `https://obi-web-production.up.railway.app`
- Obi backend (the gate, search, answers): `https://obi-backend-production.up.railway.app`

---

# Part A — What the partner builds

Five steps, in this order. Each step names exactly what we need back.

## A1. Tell us where the widget will load

Give us every **https origin** where Obi will appear, e.g. `https://base.development.omniboost.io`.
Permission is per origin, so every page on that host is covered — paths and query strings don't
matter. A page on an origin we have not listed cannot show Obi: the browser blocks it with a
`frame-ancestors` error.

## A2. Publish a signing key (JWKS)

Obi verifies every token against your **public** key. Publish it at a reachable https URL as a
standard JWKS document:

```json
{
  "keys": [
    { "kid": "base-2026-10", "kty": "RSA", "alg": "RS256", "use": "sig", "n": "<modulus>", "e": "AQAB" }
  ]
}
```

- Sign with **RS256 or ES256**. Anything else (including HS256) is rejected.
- Every key needs a **`kid`**, and every token's header must carry the `kid` it was signed with.
- To rotate: publish the new key (new `kid`) in the JWKS first, then start signing with it. Obi
  fetches an unknown `kid` from your JWKS on first sight.
- Most JWT libraries generate this JSON from your key; you don't write it by hand.

**We need back:** the JWKS URL, and the exact issuer string you put in `iss`.

## A3. Build the token endpoint (`tokenUrl`)

An endpoint on **the same origin as the page** that returns a fresh token for the logged-in user.
The widget calls it with the user's own session cookie (`credentials: "same-origin"`), so no CORS is
involved. It must answer:

```json
{ "token": "<signed JWT>" }
```

The token's claims:

| Claim | Required | Value |
|---|---|---|
| `iss` | yes | Exactly the issuer string you gave us — letter for letter. |
| `aud` | yes | `"obi"` |
| `sub` | yes | A stable id for the user. We only ever store a hash of it. |
| `iat`, `exp` | yes | Issued-at and expiry, in epoch seconds. `exp − iat` may be at most 60 minutes. |
| `source_system` | for answers per customer | The system the customer already has, e.g. `"Toast"`. |
| `target_system` | for answers per customer | The system it connects to, e.g. `"NetSuite"`. Any value is accepted. |
| `business_id` | for answers per customer | Your customer id, as a string or a number (`2108` and `"2108"` both work). |

A complete example:

```json
{
  "iss": "https://base.development.omniboost.io",
  "aud": "obi",
  "sub": "5",
  "iat": 1792072431,
  "exp": 1792072731,
  "source_system": "Toast",
  "target_system": "NetSuite",
  "business_id": 2108
}
```

- Send system **names as you have them**: `"Opera Cloud"`, `"opera-cloud"` and `"OPERA  CLOUD"` all
  match. Upper/lower case and extra spaces don't matter.
- Send the customer's real systems, unfiltered. Obi decides for itself whether to show
  (see [What Obi does with your token](#what-obi-does-with-your-token)).
- Allow for small clock differences: Obi tolerates 60 seconds of skew.

**We need back:** the deployed `tokenUrl` (not a local `.test` address), and one fresh token from
it so we can test the whole chain.

## A4. Add the widget to your page

```html
<script src="https://obi-web-production.up.railway.app/obi.js"></script>
<script>
  Obi.init({ tokenUrl: "/obi/token" });
</script>
```

- `Obi.init({ tokenUrl })` mounts the launcher button and the chat frame. Calling it again replaces
  the current widget, which is how you switch customers.
- `Obi.clear()` on logout: forgets the token and clears the chat.
- `Obi.destroy()` removes the widget completely.

**Switching customer without logging out.** When the user selects another customer or connection,
call `Obi.init({ tokenUrl })` again with a `tokenUrl` that returns a token for the new
`business_id`, `source_system` and `target_system`. Obi starts a fresh chat, so no answer carries
over between customers.

## A5. Test it

1. Open a page on a listed origin. The Obi launcher appears (or stays hidden for an unsupported
   source).
2. Open the widget and ask a question about your integration. The answer cites Omniboost pages.
3. Send us one fresh token from the deployed environment. We verify it and switch your entry on.
4. Repeat 1–2 after activation, then switch customer and check that the chat restarts.

## What Obi does with your token

| Source system in the token | Target system | What the user sees |
|---|---|---|
| Supported (Mews, Toast, Opera Cloud) | Any — known or not | Obi shows and answers from that connection's pages |
| Supported | One we have no pages for | Obi shows and answers from the source's own pages plus `obi-general` |
| Not supported or unknown (e.g. `"PEP PMS"`) | Any | Obi stays hidden — no launcher, no error |
| No token at all | — | Obi shows and answers from all indexed pages, not narrowed to a connection |
| Invalid token (bad signature, wrong `iss`, expired) | — | The chat refuses the session; fix the token |

---

# Part B — Our side

## B1. What we register per partner

Each partner is one entry in
[`knowledge-base/config/platforms.json`](../../../knowledge-base/config/platforms.json). The fields:

| Field | What it does |
|---|---|
| `issuer` | Looks up the partner from the token's `iss`. Must match exactly. |
| `jwks_url` | Where Obi fetches the partner's public keys, by `kid`. |
| `domains` | The partner's embed hosts, without scheme. **Only active entries** count: they feed the `/embed` page's `frame-ancestors` header and the frame's message allow-list. |
| `lifetime_minutes` | The longest token lifetime accepted (`exp − iat`), 1–1440; we use 60. |
| `algs` | Allowed signing algorithms: `RS256` and/or `ES256`. |
| `active` | Only an active entry is served. A token from an inactive entry is refused (401), so until activation the partner's pages send no token. |
| `allowed_integrations` | The source systems this partner may assert. A source outside it is refused (401). |

Today: `obi-test` is the only active entry. It is a temporary bridge (our own Supabase issuer) that
also carries the Base and Data Hub hosts, so their pages can load the widget before their own
entries are active. `base` and `datahub` are inactive.

**Activating a partner** (paste-ready blocks in
[partner-activation-patch.md](../5-integration-context/partner-activation-patch.md)):

1. Fill `issuer`, `jwks_url`, `domains`, `algs` from the partner's facts.
2. Check that the JWKS URL returns keys, and verify one fresh token from their deployed endpoint.
3. Validate the file under production settings, printing only the list:
   `ENV=production PLATFORMS_PATH=<abs path> uv run python -c "from app.platform.config.settings import Settings; print(Settings().platform_registry.active_platforms())"`
4. Set `active: true` and remove the partner's hosts from `obi-test`.
5. Redeploy backend and frontend (B5), then run A5 with the partner.

## B2. Supported source systems

The product catalog [`product_catalog.json`](../../../knowledge-base/config/product_catalog.json)
defines every system Obi knows (`toast`, `mews`, `opera-cloud`, `quickbooks-online`, `xero`), each
with a display name, aliases and a role (`pos`, `pms`, `accounting`). The list
**`enabled_sources`** (`mews`, `toast`, `opera-cloud`) is the set of sources that make Obi appear.
The catalog rules are in [product-catalog.md](../5-integration-context/product-catalog.md).

To support a new source system:

1. Add it to `products` in `product_catalog.json` (id, label, aliases, role).
2. Add its id to `enabled_sources`.
3. Make sure Confluence has pages labelled for it (B3), or Obi will have nothing specific to say.
4. Add it to a partner's `allowed_integrations` (and to the top-level `integrations` map) if that
   partner will send it.
5. Run `make check`, then redeploy both services — the frontend bakes the name list into `obi.js`.

## B3. Routing labels

For a token `Toast → Mews`, Obi searches only pages carrying one of four Confluence labels:
`obi-general`, `toast-general`, `mews-general`, `toast-to-pms` (the last one is the source plus the
target's role). An unknown target gives the first two only. The logic is
`build_labels` in
[`product_catalog.py`](../../../backend/app/platform/config/product_catalog.py); the design is
[ADR-directed-source-target-routing-labels](../../adr/directed-source-target-routing-labels.md) and
[ADR-routing-labels-sole-content-axis](../../adr/routing-labels-sole-content-axis.md).

A Confluence page is indexed only when it is published and carries at least one of these labels;
the label `classified` removes it. The labels in use are listed in
[routing-test-labels.md](../sync-rules/routing-test-labels.md).

## B4. The request path

1. The partner page loads `obi.js`. If a supported-source list is baked in, the script fetches the
   token once and stays hidden for an unsupported source.
2. It adds the launcher and an iframe pointing at `/embed` on the Obi frontend.
3. On click it fetches the token and posts it into the frame (to the exact Obi origin only). It
   renews the token 60 seconds before it expires.
4. The frame calls the Obi frontend's proxy (`/api/chat`, `/api/chat/visibility`). The proxy adds
   our server-side key and forwards the user token as `X-Obi-Token`.
5. The backend verifies the token
   ([`token_verifier.py`](../../../backend/app/features/rag_agent/server/token_verifier.py)), builds
   one authorization context at the gate (`_build_directed_context` in
   [`auth_context.py`](../../../backend/app/features/rag_agent/application/auth_context.py)),
   searches the four labels and answers with citations.
6. `GET /chat/visibility` answers `{"visible": false}` for an unsupported source; the frame then
   tells the loader to remove the widget (`obi:hidden`), as decided in
   [ADR-widget-hides-via-visibility-probe](../../adr/widget-hides-via-visibility-probe.md).

The token claims are defined in
[`token-claims.json`](../../../packages/contracts/src/token-claims.json); the edge check is
[ADR-signed-token-verified-at-the-edge](../../adr/signed-token-verified-at-the-edge.md).

## B5. Deploying

A git push does **not** deploy. Both services are uploaded from the repo root with the Railway CLI:

- Backend: `railway up --service obi-backend --detach`
  ([runbook](../../runbooks/railway-backend-deploy.md))
- Frontend: `scripts/deploy-frontend.sh`
  ([runbook](../../runbooks/railway-frontend-deploy.md))

`obi.js` is built with two values baked in: the Obi origin and the supported-source names. A change
to `enabled_sources` or the catalog's names therefore needs a frontend redeploy; a change to
`platforms.json` needs both. After a deploy, check `/health` on the backend and the `/embed`
`frame-ancestors` header on the frontend.

## B6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Browser: `Framing … violates … frame-ancestors` | The page's host is not on an active entry's `domains` | Add the host (B1), redeploy |
| Widget never appears | Unsupported source in the token, or the token fetch failed | Check `source_system`; open `tokenUrl` directly |
| Chat says the session is refused (401) | Bad signature, `iss` mismatch, expired token, `exp − iat` over 60 minutes, or a source the partner may not assert | Compare the token to A3 and the entry to B1 |
| Answers are not specific to the customer's connection | No token was sent, so no routing labels apply | Check that `tokenUrl` returns `{"token": …}` |
| Refused (401) right after a partner starts sending tokens | The partner's entry is still inactive | Activate the entry (B1) |
| Activation fails | JWKS URL errors (e.g. HTTP 500) or returns no `kid` | The partner fixes the JWKS (A2) |
| Token URL ends in `.test` | It is the partner's local machine | Ask for the deployed URL |

## B7. Where the truth lives

- Decisions: [ADR index](../../adr/README.md) — especially
  [ADR-source-system-decides-widget-eligibility](../../adr/source-system-decides-widget-eligibility.md),
  [ADR-directed-source-target-routing-labels](../../adr/directed-source-target-routing-labels.md),
  [ADR-routing-labels-sole-content-axis](../../adr/routing-labels-sole-content-axis.md),
  [ADR-widget-hides-via-visibility-probe](../../adr/widget-hides-via-visibility-probe.md),
  [ADR-signed-token-verified-at-the-edge](../../adr/signed-token-verified-at-the-edge.md).
- Per-partner status: [partner-facts.md](../5-integration-context/partner-facts.md).
- The gate, as built: [auth-context-gate.md](../retrieval/auth-context-gate.md).
- Config: [`platforms.json`](../../../knowledge-base/config/platforms.json),
  [`product_catalog.json`](../../../knowledge-base/config/product_catalog.json).
- Code: [`loader.ts`](../../../frontend/src/features/embed/loader.ts) (the script partners load),
  [`csp.ts`](../../../frontend/src/features/embed/csp.ts) (the `frame-ancestors` header),
  [`auth_context.py`](../../../backend/app/features/rag_agent/application/auth_context.py) (the gate),
  [`token_verifier.py`](../../../backend/app/features/rag_agent/server/token_verifier.py) (token checks).
- Local testing with simulated partners:
  [obi-embed-local-test-keys.md](../../embedding/obi-embed-local-test-keys.md).
