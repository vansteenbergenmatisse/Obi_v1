# Obi embed — local test-host keys (PLAN 11.1c, ADR-0014)

How to generate the throwaway RS256 key pairs the four `/test-hosts/*` pages use to sign a note
locally, and how the pieces wire together. Nothing here is a real secret — these are local-only
test issuers, never committed, never reachable outside your machine.

## 1. Generate the key pairs

One RSA key pair per fake platform (`mews`, `toast`, `opera`, `none`):

```bash
for name in mews toast opera none; do
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out /tmp/$name-private.pem
  openssl rsa -pubout -in /tmp/$name-private.pem -out /tmp/$name-public.pem
done
```

## 2. Put them in `apps/web/.env.local`

Paste each PEM (including the `BEGIN`/`END` lines) as a double-quoted, multi-line value:

```
TEST_OBI_PRIVATE_KEY_MEWS="-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----"
TEST_OBI_PUBLIC_KEY_MEWS="-----BEGIN PUBLIC KEY-----
...
-----END PUBLIC KEY-----"
```

Repeat for `TOAST`, `OPERA`, `NONE`. See `apps/web/.env.example` for the full list of variable
names. `apps/web/.env.local` is gitignored — nothing here ever gets committed.

## 3. Point both apps at the local platform registry

`config/platforms.local.json` (committed — it holds only public issuer metadata, no keys) defines
four test issuer entries (`test-mews`/`test-toast`/`test-opera`/`test-none`, all `active: true`,
domain `localhost:3000`) and maps the JWT `integration` claim values (`mews`/`toast`/`opera-cloud`)
to the live `obi-*-test` knowledge scopes — the same `integrations` map shape as the real committed
`config/platforms.json`.

Point the **frontend** at it (same env var name as the backend's `PLATFORMS_PATH` setting):

```bash
# apps/web/.env.local
PLATFORMS_PATH=/absolute/path/to/repo/config/platforms.local.json
```

Point the **backend** at it too, so `apps/automation`'s `TokenVerifier` trusts the same test
issuers (its own `Settings.platforms_path` / `PLATFORMS_PATH` env var, `allow_empty_platforms`
already defaults true in local/test):

```bash
# apps/automation/.env or shell
PLATFORMS_PATH=/absolute/path/to/repo/config/platforms.local.json
```

## 4. Run it

```bash
# backend
cd apps/automation && PLATFORMS_PATH=.../config/platforms.local.json uvicorn app.main:app

# frontend
cd apps/web && CHAT_API_KEY=<matches backend chat_api_key> APP_ENV=local \
  PLATFORMS_PATH=.../config/platforms.local.json pnpm run dev
```

Open `http://localhost:3000/test-hosts/{none,mews,toast,opera-cloud}` — each is a bare page
simulating a third-party site with nothing but the `obi.js` paste template. Click the round
launcher button in the corner to open the chat, scoped by that page's token.

## How the pieces fit

- `apps/web/src/app/api/test-hosts/[name]/obi-token/route.ts` signs a 60-minute RS256 JWT with
  `TEST_OBI_PRIVATE_KEY_<NAME>`, `kid: "test-<name>-1"`, `iss` = that test issuer, `aud: "obi"`,
  and (except for `none`) `company_id`/`company_name`/`integration` business claims.
- `apps/web/src/app/.well-known/<issuer>/obi-jwks.json` (via a `next.config.ts` rewrite to
  `/api/test-hosts/jwks/[issuer]`, a real Node.js route) serves the matching PUBLIC key
  (`TEST_OBI_PUBLIC_KEY_<NAME>`) as a JWKS document, `kid`-matched to the token.
- The backend's `TokenVerifier` fetches that JWKS URL (recorded in `config/platforms.local.json`)
  to verify the token's signature, exactly like a real platform's issuer.

## Regenerating

These keys are throwaway — regenerate them any time (e.g. if `.env.local` gets reset) by
repeating step 1. There is no rotation ceremony; a local dev restart picks up new values.
