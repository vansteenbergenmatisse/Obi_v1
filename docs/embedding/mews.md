# Obi embed — Mews hand-over pack

**Phase 11.1c (ADR-0014).** Everything Mews needs to embed Obi, and the four values we need back
to switch it on. Until those four are filled in `config/platforms.json` and `active` is flipped to
`true`, the `mews` entry stays inactive: the frame's CSP won't list your domain and the loader
won't run there, but a token that arrives is still verified.

## 1. Add the widget (one script tag)

```html
<script src="https://<obi-embed-origin>/obi.js"></script>
<script>
  Obi.init({ tokenUrl: "/obi/token" });
</script>
```

`tokenUrl` is an endpoint **on your own server** that mints the short-lived note (below). `obi.js`
fetches it at button-click with `credentials: "same-origin"` (your session cookie rides; no CORS),
posts it into the Obi iframe, and sends it as `Authorization: Bearer <jwt>` on every chat call.

## 2. Mint the note (short-lived signed JWT)

Sign with **RS256 or ES256** (never HS256), include a `kid` header, and set exactly these claims.
Business values are **all-three-or-none**: include all of `company_id` / `company_name` /
`integration`, or none (a note with none scopes to general content only).

| claim | value |
|---|---|
| `iss` | your issuer URL (what you give us in §4) |
| `aud` | `obi` (literal) |
| `sub` | stable per-user id (only a hash is ever stored) |
| `iat` / `exp` | issued-at / expiry; `exp - iat` ≤ 60 minutes |
| `company_id` | your opaque customer id (audit only) |
| `company_name` | display name (audit only) |
| `integration` | **`mews`** (the only value that maps to knowledge scope) |

**Reference — Node (`jose`):**

```js
import { SignJWT, importPKCS8 } from "jose";

const key = await importPKCS8(process.env.OBI_PRIVATE_KEY, "RS256");
export async function mintObiToken(user, company) {
  const now = Math.floor(Date.now() / 1000);
  return new SignJWT({ company_id: company.id, company_name: company.name, integration: "mews" })
    .setProtectedHeader({ alg: "RS256", kid: "obi-mews-1" })
    .setIssuer("https://app.mews.com").setAudience("obi").setSubject(user.id)
    .setIssuedAt(now).setExpirationTime(now + 3600).sign(key);
}
```

**Reference — Python (`pyjwt[crypto]`):**

```python
import time, jwt

def mint_obi_token(user_id: str, company_id: str, company_name: str) -> str:
    now = int(time.time())
    return jwt.encode(
        {"iss": "https://app.mews.com", "aud": "obi", "sub": user_id, "iat": now, "exp": now + 3600,
         "company_id": company_id, "company_name": company_name, "integration": "mews"},
        OBI_PRIVATE_KEY_PEM, algorithm="RS256", headers={"kid": "obi-mews-1"},
    )
```

Publish the **public** key(s) as a JWKS at a stable HTTPS URL (rotate by adding a new `kid`, never
by reusing one). We fetch it by `kid`, cached, with a finite timeout.

## 3. Done when

1. The round button appears on your page; clicking it opens the chat.
2. A signed-in user gets answers scoped to **Mews + general** content — never another platform's.
3. A user with no business values (or no token) gets **general** content only.
4. A tampered / expired / wrong-`aud` / wrong-issuer token is refused (401) before any search, and
   the loader silently renews once.
5. A cross-origin / non-parent `postMessage` into the frame is ignored.
6. The token is never in a cookie, `localStorage`, `sessionStorage`, or the URL.

## 4. What we need back (the four values)

1. **Issuer** — the `iss` you sign with (hint: `https://app.mews.com`).
2. **JWKS URL** — where your public keys live (e.g. `https://app.mews.com/.well-known/obi-jwks.json`).
3. **Browser domain(s)** — where the widget runs, for the frame's `frame-ancestors` CSP
   (hint: `app.mews.com`).
4. **Integration value** — confirm it is `mews` (maps to the `obi-mews-test` knowledge scope).

Also: one test company on Mews and one signed-in test user, so we can prove isolation end-to-end.

## 5. The one line that activates Mews

In `config/platforms.json`, fill the `mews` entry's `issuer` / `jwks_url` / `domains` from §4 and
flip:

```json
"mews": { "...": "...", "active": true }
```

Validated at startup: the mapped scope must exist in `config/knowledge_scopes.json` (`obi-mews-test` does),
and `active:true` requires a real issuer/JWKS/domains (no `PLACEHOLDER`).
