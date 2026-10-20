# Obi embed — local test-host keys (ADR-db-level-customer-scope-isolation-backstop)

How to generate the throwaway RS256 key pairs the `/test-hosts/*` pages use to sign a note
locally, and how the pieces wire together. Nothing here is a real secret — these are local-only
test issuers, never committed, never reachable outside your machine.

For how a real partner (Base, Data Hub) integrates, see
[`docs/Final_docs/1-how-partners-integrate-with-obi/how-partners-integrate-with-obi.md`](../Final_docs/1-how-partners-integrate-with-obi/how-partners-integrate-with-obi.md).

## 1. Generate the key pairs

One RSA key pair per fake host (`mews`, `toast`, `opera`, `none`, and optionally `quickbooks`):

```bash
for name in mews toast opera none; do
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out /tmp/$name-private.pem
  openssl rsa -pubout -in /tmp/$name-private.pem -out /tmp/$name-public.pem
done
```

## 2. Put them in `frontend/.env.local`

Paste each PEM (including the `BEGIN`/`END` lines) as a double-quoted, multi-line value:

```
TEST_OBI_PRIVATE_KEY_MEWS="-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----"
TEST_OBI_PUBLIC_KEY_MEWS="-----BEGIN PUBLIC KEY-----
...
-----END PUBLIC KEY-----"
```

Repeat for `TOAST`, `OPERA`, `NONE`. See `frontend/.env.example` for the variable names.
`frontend/.env.local` is gitignored — nothing here ever gets committed.

`TEST_OBI_PRIVATE_KEY_QUICKBOOKS` / `TEST_OBI_PUBLIC_KEY_QUICKBOOKS` are optional: they only
feed the disabled-source demo (`/test-hosts/quickbooks`, see below). They are not listed in
`frontend/.env.example`, and `platforms.local.json` has no `test-quickbooks` issuer, so the
backend cannot verify that token — the loader hides the widget from the decoded
`source_system` alone.

## 3. Point both apps at the local platform registry

`knowledge-base/config/platforms.local.json` (committed — it holds only public issuer metadata,
no keys) defines four test issuer entries (`test-mews`/`test-toast`/`test-opera`/`test-none`,
all `active: true`, domains `localhost:3000` and `localhost:3100`, JWKS served from
`http://localhost:3100/.well-known/<issuer>/obi-jwks.json`).

Point the **frontend** at it (same env var name as the backend's `PLATFORMS_PATH` setting):

```bash
# frontend/.env.local
PLATFORMS_PATH=/absolute/path/to/repo/knowledge-base/config/platforms.local.json
```

Point the **backend** at it too, so its `TokenVerifier` trusts the same test issuers
(`Settings.platforms_path` / `PLATFORMS_PATH`, read from `backend/.env`, the root `.env`, or the
shell; `allow_empty_platforms` already defaults true in local/test):

```bash
# root .env or shell
PLATFORMS_PATH=/absolute/path/to/repo/knowledge-base/config/platforms.local.json
```

## 4. Run it

```bash
make api        # backend on :8000
make embed-dev  # frontend on :3100 (rebuilds public/obi.js first)
```

Use port 3100, not 3000: the JWKS URLs in `platforms.local.json` point at `localhost:3100`, so a
token minted on another port does not verify.

Open `http://localhost:3100/test-hosts/{none,mews,toast,opera-cloud}` — each is a bare page
simulating a host site with nothing but the `obi.js` paste template. Click the round launcher
in the corner to open the chat. Also available: `/test-hosts/multi`,
`/test-hosts/connection-switch`, and `/test-hosts/quickbooks` (the widget must stay hidden).

## How the pieces fit

- `frontend/src/app/api/test-hosts/[name]/obi-token/route.ts` signs a 60-minute RS256 JWT with
  `TEST_OBI_PRIVATE_KEY_<NAME>`, `kid: "test-<name>-1"`, `iss` = that test issuer, `aud: "obi"`.
  - With `?form=directed` it emits the directed claims (`source_system`, `target_system`,
    `business_id`) — the current contract. The `toast`, `opera-cloud` and `quickbooks` hosts
    have a directed demo.
  - Without it, it emits the legacy `company_id`/`company_name`/`integration` claims (none for
    `none`). The backend still accepts that form, but it no longer routes content.
- Per ADR-source-system-decides-widget-eligibility only the token's `source_system` decides
  whether Obi shows: `enabled_sources` in `knowledge-base/config/product_catalog.json` is
  `mews`, `toast`, `opera-cloud`. The `quickbooks` host's source (`quickbooks-online`) is not
  enabled, so the widget stays hidden.
- `/.well-known/<issuer>/obi-jwks.json` is rewritten in `frontend/next.config.ts` to
  `frontend/src/app/api/test-hosts/jwks/[issuer]/route.ts`, which serves the matching PUBLIC key
  (`TEST_OBI_PUBLIC_KEY_<NAME>`) as a JWKS document, `kid`-matched to the token.
- The backend's `TokenVerifier` fetches that JWKS URL (recorded in `platforms.local.json`) to
  verify the token's signature, exactly like a real platform's issuer.
- Host configuration (issuers, kids, claims) lives in `frontend/src/app/api/test-hosts/config.ts`.

## Regenerating

These keys are throwaway — regenerate them any time (e.g. if `.env.local` gets reset) by
repeating step 1. There is no rotation ceremony; a local dev restart picks up new values.
