# Obi embed — Data Hub hand-over pack

**Phase 11.1c (ADR-0014).** Everything the Data Hub needs to embed Obi, and the values we need back
to switch it on. The Data Hub is a **hub**: it embeds Obi for many customers, and each customer runs
an underlying PMS/POS (Mews, Toast, or Opera Cloud). So the Data Hub's note carries the **customer's
underlying integration** as its `integration` claim — not the literal string `datahub` — and that
value is what maps to knowledge scope. Obi trusts the Data Hub to assert only integrations in its
allow-list (`mews`, `toast`, `opera-cloud`).

> **Status today.** The `datahub` entry already exists in `config/platforms.json` and is `active`,
> but its `issuer` / `jwks_url` are placeholders (`TODO until 4.x`). Because of that, a real
> production boot **fails closed on purpose** until the four values in §4 are filled in — the frame's
> CSP won't list your domain and the loader won't run there. This is the guard working, not a bug.

## 1. Add the widget (one script tag)

```html
<script src="https://<obi-embed-origin>/obi.js"></script>
<script>
  Obi.init({ tokenUrl: "/obi/token" });
</script>
```

`tokenUrl` is an endpoint **on your own server** that mints the short-lived note (below). `obi.js`
fetches it at button-click with `credentials: "same-origin"` (your session cookie rides; no CORS),
posts it into the Obi iframe, and sends it as `Authorization: Bearer <jwt>` on every chat call. The
token lives in memory only — never a cookie, `localStorage`, `sessionStorage`, or the URL.

**One embed, per-customer scope.** You ship the same script tag to every customer. What scopes each
answer is the `integration` claim you put in that customer's note (§2) — you do not need a different
snippet or a different link per customer.

## 2. Mint the note (short-lived signed JWT)

Sign with **RS256 or ES256** (never HS256), include a `kid` header, and set exactly these claims.
Business values are **all-three-or-none**: include all of `company_id` / `company_name` /
`integration`, or none (a note with none scopes to general content only).

| claim | value |
|---|---|
| `iss` | your Data Hub issuer URL (what you give us in §4) |
| `aud` | `obi` (literal) |
| `sub` | stable per-user id (only a hash is ever stored) |
| `iat` / `exp` | issued-at / expiry; `exp - iat` ≤ 60 minutes |
| `company_id` | the customer's opaque id (audit only) |
| `company_name` | the customer's display name (audit only) |
| `integration` | the customer's underlying platform: **`mews`**, **`toast`**, or **`opera-cloud`** |

The `integration` value is the one thing that decides which corpus the user can see. Set it from the
customer's actual PMS/POS in your own records — a Mews customer gets `mews`, a Toast customer gets
`toast`, an Opera Cloud customer gets `opera-cloud`. Anything outside your allow-list is refused
(401); a note with no business trio gets general content only.

**Reference — Node (`jose`):**

```js
import { SignJWT, importPKCS8 } from "jose";

const key = await importPKCS8(process.env.OBI_PRIVATE_KEY, "RS256");
export async function mintObiToken(user, customer) {
  const now = Math.floor(Date.now() / 1000);
  // customer.integration is one of "mews" | "toast" | "opera-cloud"
  return new SignJWT({
    company_id: customer.id, company_name: customer.name, integration: customer.integration,
  })
    .setProtectedHeader({ alg: "RS256", kid: "obi-datahub-1" })
    .setIssuer("https://<your-datahub-issuer>").setAudience("obi").setSubject(user.id)
    .setIssuedAt(now).setExpirationTime(now + 3600).sign(key);
}
```

**Reference — Python (`pyjwt[crypto]`):**

```python
import time, jwt

def mint_obi_token(user_id: str, company_id: str, company_name: str, integration: str) -> str:
    # integration is one of "mews" | "toast" | "opera-cloud"
    now = int(time.time())
    return jwt.encode(
        {"iss": "https://<your-datahub-issuer>", "aud": "obi", "sub": user_id,
         "iat": now, "exp": now + 3600, "company_id": company_id,
         "company_name": company_name, "integration": integration},
        OBI_PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": "obi-datahub-1"},
    )
```

Publish the **public** key(s) as a JWKS at a stable HTTPS URL (rotate by adding a new `kid`, never by
reusing one). We fetch it by `kid`, cached, with a finite timeout.

## 3. Test on localhost first (before you give us anything)

You do not need our production config to prove the flow end-to-end on your machine:

1. Generate a throwaway RS256 key pair and stand up your `tokenUrl` locally (see
   `docs/embedding/obi-embed-local-test-keys.md`).
2. Run the widget against the local Obi build. The committed `config/platforms.local.json` already
   defines local test issuers on `localhost:3000` and maps the `mews` / `toast` / `opera-cloud`
   integration values to the live `obi-*-test` knowledge scopes — the same map shape as production.
3. Mint a note with `integration: "mews"` and confirm the user gets Mews + general answers; mint one
   with `integration: "toast"` and confirm they get Toast + general and **never** Mews content.

## 4. Done when

1. The round button appears on a Data Hub page; clicking it opens the chat.
2. A signed-in user gets answers scoped to **their customer's integration + general** content —
   never another platform's.
3. A user with no business values (or no token) gets **general** content only.
4. A tampered / expired / wrong-`aud` / wrong-issuer token is refused (401) before any search, and
   the loader silently renews once.
5. A cross-origin / non-parent `postMessage` into the frame is ignored.
6. The token is never in a cookie, `localStorage`, `sessionStorage`, or the URL.

## 5. What we need back

1. **Issuer** — the `iss` your Data Hub signs with (replaces the `TODO until 4.x` placeholder).
2. **JWKS URL** — where your public keys live (e.g. `https://<datahub>/.well-known/obi-jwks.json`).
3. **Browser domain(s)** — where the widget runs, for the frame's `frame-ancestors` CSP.
4. **Allowed integrations** — confirm the Data Hub should be trusted to assert `mews`, `toast`, and
   `opera-cloud` (this is the committed default; tell us to add or drop any). Each maps to its
   `obi-<name>-test` knowledge scope.

Also: one test customer per integration and one signed-in test user each, so we can prove
cross-integration isolation end-to-end.

## 6. The one change that activates the Data Hub

In `config/platforms.json`, fill the `datahub` entry's `issuer` / `jwks_url` / `domains` from §4
(replacing the placeholders). It is already `active: true` and already lists
`allowed_integrations: ["mews", "toast", "opera-cloud"]`:

```json
"datahub": {
  "issuer": "https://<your-datahub-issuer>",
  "jwks_url": "https://<datahub>/.well-known/obi-jwks.json",
  "domains": ["<datahub-domain>"],
  "lifetime_minutes": 60,
  "algs": ["RS256"],
  "active": true,
  "allowed_integrations": ["mews", "toast", "opera-cloud"]
}
```

Validated at startup: each `allowed_integrations` value must exist in the `integrations` map (all
three do), each mapped scope must exist in `config/knowledge_scopes.json`, and `active: true` outside
local requires a real **https** issuer/JWKS on a real (non-localhost, non-`.local`) host with no
`TODO`/`PLACEHOLDER` marker — which is why the placeholder entry cannot go live as-is.

## 7. What Obi guarantees back

- The request body never decides access: scope, company, and integration come only from the verified
  note. A body that disagrees is ignored and logged.
- Answers cite real sources or refuse with a reason — no guessing.
- Nothing crosses integrations at the database itself (row-level security), not just in app code.
