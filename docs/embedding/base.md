# Obi embed — Base hand-over pack

**Phase 11.1c (ADR-0014).** Everything Base needs to embed Obi, and the values we need back to
switch it on. Like the Data Hub, Base is a **hub**: it embeds Obi for many customers, each running an
underlying PMS/POS (Mews, Toast, or Opera Cloud). So Base's note carries the **customer's underlying
integration** as its `integration` claim — not the literal string `base` — and that value is what
maps to knowledge scope.

> **Status today.** Base is **not yet a configured platform.** There is no `base` entry in
> `config/platforms.json`, so a Base-signed token is refused until we add one (§6) and fill the
> values in §5. Everything below is what makes that entry real. (The other platforms — `datahub`,
> `mews`, `toast`, `opera-cloud` — already have entries; Base is the one that has to be created.)

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
answer is the `integration` claim you put in that customer's note (§2) — no per-customer snippet or
link needed.

## 2. Mint the note (short-lived signed JWT)

Sign with **RS256 or ES256** (never HS256), include a `kid` header, and set exactly these claims.
Business values are **all-three-or-none**: include all of `company_id` / `company_name` /
`integration`, or none (a note with none scopes to general content only).

| claim | value |
|---|---|
| `iss` | your Base issuer URL (what you give us in §5) |
| `aud` | `obi` (literal) |
| `sub` | stable per-user id (only a hash is ever stored) |
| `iat` / `exp` | issued-at / expiry; `exp - iat` ≤ 60 minutes |
| `company_id` | the customer's opaque id (audit only) |
| `company_name` | the customer's display name (audit only) |
| `integration` | the customer's underlying platform: **`mews`**, **`toast`**, or **`opera-cloud`** |

The `integration` value is the one thing that decides which corpus the user can see. Set it from the
customer's actual PMS/POS in your own records. Anything outside the allow-list we configure for Base
is refused (401); a note with no business trio gets general content only.

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
    .setProtectedHeader({ alg: "RS256", kid: "obi-base-1" })
    .setIssuer("https://<your-base-issuer>").setAudience("obi").setSubject(user.id)
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
        {"iss": "https://<your-base-issuer>", "aud": "obi", "sub": user_id,
         "iat": now, "exp": now + 3600, "company_id": company_id,
         "company_name": company_name, "integration": integration},
        OBI_PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": "obi-base-1"},
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

1. The round button appears on a Base page; clicking it opens the chat.
2. A signed-in user gets answers scoped to **their customer's integration + general** content —
   never another platform's.
3. A user with no business values (or no token) gets **general** content only.
4. A tampered / expired / wrong-`aud` / wrong-issuer token is refused (401) before any search, and
   the loader silently renews once.
5. A cross-origin / non-parent `postMessage` into the frame is ignored.
6. The token is never in a cookie, `localStorage`, `sessionStorage`, or the URL.

## 5. What we need back

1. **Issuer** — the `iss` your Base platform signs with.
2. **JWKS URL** — where your public keys live (e.g. `https://<base>/.well-known/obi-jwks.json`).
3. **Browser domain(s)** — where the widget runs, for the frame's `frame-ancestors` CSP.
4. **Allowed integrations** — which of `mews` / `toast` / `opera-cloud` Base should be trusted to
   assert (tell us the set; each maps to its `obi-<name>-test` knowledge scope).

Also: one test customer per integration and one signed-in test user each, so we can prove
cross-integration isolation end-to-end.

## 6. The change that activates Base (a new platform entry)

Base has no entry yet, so we **add** one to `config/platforms.json` (`base` is not otherwise a
reserved word in the code — it is created exactly like `datahub`):

```json
"base": {
  "issuer": "https://<your-base-issuer>",
  "jwks_url": "https://<base>/.well-known/obi-jwks.json",
  "domains": ["<base-domain>"],
  "lifetime_minutes": 60,
  "algs": ["RS256"],
  "active": true,
  "allowed_integrations": ["mews", "toast", "opera-cloud"]
}
```

Validated at startup: each `allowed_integrations` value must exist in the `integrations` map (the
three above do), each mapped scope must exist in `config/knowledge_scopes.json`, and `active: true`
outside local requires a real **https** issuer/JWKS on a real (non-localhost, non-`.local`) host with
no `TODO`/`PLACEHOLDER` marker. Adding `base` is a config-only change — no code change — because the
platform registry is data-driven.

## 7. What Obi guarantees back

- The request body never decides access: scope, company, and integration come only from the verified
  note. A body that disagrees is ignored and logged.
- Answers cite real sources or refuse with a reason — no guessing.
- Nothing crosses integrations at the database itself (row-level security), not just in app code.
