# DRAFT — Jasper reply + platform entries (substep 8.5.3)

> **DRAFT — the owner edits and sends this. The AI never sends it.** Produced for action-plan
> substep `8.5.3 · The Jasper reply and the platform entries`. Nothing here was sent,
> deployed, or written into `platforms.json`. Source: `research-jasper-handoff.md` (this folder),
> plus facts verified in this session (noted inline). Owner placeholders are marked
> `[OWNER: …]`.

---

## 1. Email draft (ready to send after owner edits)

**Subject:** Obi widget embed — the contract, and what we need from your side

Hi Jasper,

Here is everything you need to embed Obi on Base and Data Hub, plus the few things I need back
from you to wire it up.

### The embed contract

Two tags on your page. One loads the widget, one starts it:

```html
<script src="https://obi-web-production.up.railway.app/obi.js"></script>
<script>
  Obi.init({ tokenUrl: "/your/obi-token-endpoint" });
</script>
```

`obi.js` draws the launcher, opens the chat panel in an iframe served from our domain, fetches a
short-lived signed token from your `tokenUrl` when the user opens the chat, renews it before it
expires, and drops it on `Obi.clear()`.

`tokenUrl` is the only option. It points at an endpoint on your own server (same origin as the
page), so the user's existing session cookie rides along and there is no CORS to configure. Scope
and integration never appear in this snippet. They travel inside the signed token as claims (see
below), so the page markup is identical across every tenant.

Two notes on the URL:

- `https://obi-web-production.up.railway.app/obi.js` is the real, deployed loader as of
  2026-10-09. You can embed against it today.
- That is the Railway host we run the frontend on now. We plan to move it behind a branded
  `obi.omniboost.com` later. When we do, the only change on your side is the `src` URL, and I will
  give you plenty of notice. `[OWNER: confirm whether to mention the branded URL now or leave it out.]`

### What I need from you

To verify a tenant and let real authenticated chat through, I need five things per platform (Base
and Data Hub):

1. **Issuer string** — the `iss` value your tokens will carry. One per platform is fine.
2. **A reachable JWKS URL** — your public keys, served as JWKS, keyed by `kid`. Keys must be
   **RS256 or ES256** (we do not accept HS256). We fetch and cache this; it must stay reachable.
3. **Embed domain(s)** — the exact origins the widget loads on. I have these as
   `base.omniboost.io` (Base) and `datahub.omniboost.io` (Data Hub). Please confirm, and add any
   others (staging, preview). These lock the iframe's `frame-ancestors`, so a missing one blocks
   the embed.
4. **The integration value(s) the hub vends** — the exact `integration` string(s) your token
   endpoint will assert. We map each to a set of knowledge scopes on our side.
5. **A token-minting endpoint** (the `tokenUrl` above) that signs a JWT with:
   - `iss` — your issuer string (item 1)
   - `aud` — exactly `"obi"`
   - `sub` — the end user's stable id
   - `iat` / `exp` — issued-at and expiry, lifetime **60 minutes or less**
   - `company_id`, `company_name`, `integration` — **all three present, or none.** Partial sets
     are rejected.

That is the whole contract. Once I have those five, I add your entries on our side and we test.

### The test plan (four cases)

Here is how we will prove each tenant, and which behaviors work today versus later:

| Case | What it checks | Status |
|---|---|---|
| Single integration | One `integration` claim resolves to its scopes and the user gets answers from exactly that scope | **Works today** |
| Multiple integrations | One user spanning several integrations in one session | **Future** — the multi-slot contract is designed but not built end to end yet; today a token carries one `integration` string |
| Unsupported integration | An `integration` your issuer is not allowed to vend is refused | **Works today** (returns 401) |
| Revoked scope | Turning an integration off stops answers for it | **Works today** via a config change on our side; it takes effect within the token's lifetime (≤60 min). There is no instant per-token kill switch |

### One honest status note

Real authenticated chat in production depends on your platform integration being live — the
issuer, the public JWKS, and the per-platform token endpoint above. That is not stood up yet on
either side, so this is the step that unblocks it. Our current signing keys are a local test
harness only; they are not something you can point at.

To test before your production endpoints are ready, we need a JWKS we can both reach. Two options:

- **[OWNER: option A]** You stand up a staging JWKS endpoint (and a staging token endpoint), and we
  verify against that first.
- **[OWNER: option B]** We use our local test-host harness as the stand-in to prove the wiring,
  then swap in your real issuer when it is ready.

`[OWNER: pick one and state it here before sending.]`

Happy to jump on a call to walk through any of this.

Best,
`[OWNER: name]`

---

## 2. What happens after you send

Once Jasper replies with the five facts, the work on our side, in order:

1. Add a `platforms.json` entry for each platform (Base, Data Hub) with his issuer, JWKS URL and
   embed domain(s), set **`active: false`** until his endpoints verify.
2. Map each `integration` value he vends to its knowledge scopes.
3. Verify his JWKS is reachable and his token endpoint mints a conforming JWT (correct `iss`,
   `aud:"obi"`, `sub`, `iat`, `exp` ≤ 60 min, and the three business claims all-or-none).
4. Flip the entry to **`active: true`** only after that verification passes.
5. Redeploy the backend (new registry entry) and rebuild/redeploy the frontend (the iframe's
   `frame-ancestors` CSP derives from the active embed domains).
6. Remove the temporary `obi-test` issuer and its embed allow-list entry once the real platforms
   are active.
7. Run the four-case matrix against the deployed origin and save the outputs where the plan's
   Proof line says, so each case lands as stated (works-today vs future).

Entries go active only after verification, never on receipt of the email.
