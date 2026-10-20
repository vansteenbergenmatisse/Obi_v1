# Partner replies — the directed-connection contract (substep 9.6.1)

> **DRAFTS — the owner edits and sends these. The AI never sends them.** Produced for action-plan
> substep `9.6.1` (Option A, ADR-directed-source-target-routing-labels). Nothing here was sent, deployed, or written into
> `platforms.json`. Owner placeholders are marked `[OWNER: …]`.
>
> These express the **directed `source_system` → `target_system` + `business_id`** contract — the
> form Obi now routes on (ADR-directed-source-target-routing-labels, confirmed decision `connection-routing`). They **supersede the
> three-slot `context.slots` version** (an earlier Jasper reply draft, since removed). Base and Data Hub each join exactly two systems — a source and a
> target (`plan.md` §D.17) — so the directed pair is their real shape, not a simplification.

---

## The contract both partners get

### The embed snippet

Two tags on the page. One loads the widget, one starts it:

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
page), so the user's session cookie rides along and there is no CORS to set up. The connection
never appears in this snippet. It travels inside the signed token as claims, so the page markup is
the same for every customer.

Two notes on the URL:

- The `<script src>` is the **web** host, `obi-web-production.up.railway.app/obi.js`. An earlier
  thread gave the **backend** host (`obi-backend-production.up.railway.app`) — that host is the API
  the widget sends chat to, not the script source. Embed against the web host.
- That is the Railway host we run the frontend on for the **test phase**. We move it behind a
  branded `obi.omniboost.com` **before go-live**; the only change on your side is the `src` URL,
  and you get a heads-up well ahead of the switch.

### The token: a directed connection

Each chat is one directed connection — a `source_system`, a `target_system`, and the customer id.
Your token endpoint signs a JWT like this:

```json
// header
{ "alg": "RS256", "kid": "<your kid>" }
// payload
{
  "iss": "https://<your-domain>",
  "aud": "obi",
  "sub": "<stable user id>",
  "business_id": "<customer id>",
  "source_system": "toast",
  "target_system": "mews",
  "iat": <now>, "exp": <now + 3600 max>
}
```

- `source_system` and `target_system` are the two products the connection joins, as canonical
  catalog ids (we also resolve common aliases). **Direction matters**: `toast → mews` is a
  different connection from `mews → toast`, and Obi answers for the one you send.
- Obi derives each system's role (POS, PMS, accounting) from the product id. You send ids, not role
  labels.
- One directed connection per chat. A different connection is a new token, which starts a fresh
  chat on its own.
- Known ids today: POS `toast`; PMS `mews`, `opera-cloud`; accounting `quickbooks-online`, `xero`.
  The **source** of a connection is always one of `mews`, `opera-cloud`, `toast` (a chat starts from
  a PMS or a POS). Accounting is a **target only** — `mews → quickbooks-online` is valid, but a chat
  never starts from an accounting product. We route a connection when it has pages and refuse with a
  reason when its box is empty, so send the real pair and we will tell you what is covered.
- Only the **source** decides whether Obi shows (ADR-source-system-decides-widget-eligibility,
  2026-10-20): Mews, Toast and Opera Cloud are supported sources. An unknown or unsupported source
  hides the widget (403 `source_not_enabled`). The target is never checked: send the customer's real
  target, even one we have no pages for; it then gets general and source answers.
- Send two ids, never a compound. A value like `toast-opera` is not a system — it reads as two ids
  mashed together and resolves to nothing; as a source it hides Obi. Send `toast` as the source and
  the PMS id as the target.
- The legacy single-`integration` claim and the `context.slots` form still verify, but they no
  longer route — the directed pair is what Obi filters on. New tokens send the directed form.
- `aud` is exactly `"obi"`, `sub` is the end user's stable id, `iss` is your issuer string, and
  `exp` is 60 minutes or less after `iat`. The customer id (`business_id`) scopes the chat; it is
  never a name and never logged in the clear.

### What I need from you, per platform

1. **Issuer string** — the `iss` your tokens carry. One per platform is fine.
2. **A reachable JWKS URL** — your public keys as JWKS, keyed by `kid`, **RS256 or ES256** (not
   HS256). We fetch and cache it; it has to stay reachable.
3. **Embed domain(s)** — the exact origins the widget loads on. These lock the iframe's
   `frame-ancestors`, so a missing one blocks the embed.
4. **Which source and target your hub vends, per customer** — the canonical ids your token endpoint
   will put in `source_system` and `target_system`. This is the one answer that drives routing:
   for each customer, which product is the source and which is the target.
5. **A token-minting endpoint** (the `tokenUrl` above) that signs the directed JWT shown.

### The test plan

| Case | What it checks | Status |
|---|---|---|
| Directed connection | A `source → target` pair resolves and the user gets answers from that connection's pages only | **Works today** (the directed gate + hard label filter are built and tested) |
| Wrong-connection isolation | A different connection's pages never appear, at any similarity | **Works today** (proven at the DB + eval level; `phase-9-isolation-run.txt`) |
| Unsupported source | A source not in the catalog or not enabled hides the widget; a known source your issuer may not vend is refused | **Works today** (403 `source_not_enabled` before any search, or 401 on a vend violation; ADR-source-system-decides-widget-eligibility) |
| Any target | The target is never checked; an unknown target still gets general + source answers | **Works today** (routes on `[obi-general, {source}-general]`) |
| Direction swap | `source` and `target` swapped is treated as a new connection and resets the chat | **Works today** (widget + session) |
| Empty connection box | A valid pair with no pages yet refuses with a reason, not a wrong answer | **Works today** (content-gated) |

### One honest status note

Real authenticated chat in production needs your platform integration live — the issuer, the public
JWKS, and the per-platform token endpoint. That is not stood up yet on either side, so this is the
step that unblocks it. Our current signing keys are a local test harness only.

To test before your production endpoints are ready, we need a JWKS we can both reach:

- **[OWNER: option A]** You stand up a staging JWKS + token endpoint, and we verify against that.
- **[OWNER: option B]** We use our local test-host harness to prove the wiring, then swap in your
  real issuer when it is ready.

`[OWNER: pick one before sending.]`

---

## 1. Email to Jasper

**Subject:** Obi widget embed — the directed-connection contract, and what I need from you

Hi Jasper,

Here is the full contract for embedding Obi on **Data Hub**, plus the few facts I need back to wire
it up.

Everything is in the shared contract above: the two-tag snippet, the directed token, the five
things I need, and the test plan. The one point to settle on a call is item 4 — **for each
customer, which product is the source and which is the target.** Your hub joins two systems per
customer; tell us which is which and Obi routes to exactly that connection's pages.

One correction to earlier threads: embed against the **web** host
(`obi-web-production.up.railway.app/obi.js`), not the backend host. And your sample token used
`toast-opera` — that is not a system, so the gate refuses it with a 401. Send `toast` as the source
and the PMS id as the target, as two separate ids.

Once I have the five facts, I add your entries on our side and we test.

Happy to jump on a call to walk through any of it.

Best,
`[OWNER: name]`

**P.S.** The `obi.js` URL above is the test-phase host. It moves to `obi.omniboost.com` before
go-live, and the only change on your side is that one `src` line — you will hear from me well ahead.

---

## 2. Email to Marien

**Subject:** Obi widget embed — the directed-connection contract, and what I need from you

Hi Marien,

Same contract as the one going to Jasper, for **Base**. The snippet, the directed token, the five
facts, and the test plan are all in the shared contract above.

The one answer that drives everything is item 4 — **per customer, which product is the source and
which is the target.** Your hub joins two systems per customer; name the source and the target and
Obi filters to that connection's pages, nothing else.

Two things worth flagging up front: embed against the **web** host
(`obi-web-production.up.railway.app/obi.js`), not the backend host; and send the two systems as
separate canonical ids, never a compound string — a mashed value resolves to nothing and the gate
refuses the token.

Send me the five facts and I will add your entries and we test.

Call any time to walk through it.

Best,
`[OWNER: name]`

**P.S.** The `obi.js` URL is the test-phase host; it moves to `obi.omniboost.com` before go-live,
and you get a heads-up before the `src` changes.

---

## What happens after they reply

For each platform, once the five facts are in, on our side in order:

1. Add a `platforms.json` entry (issuer, JWKS URL, embed domains, the source/target ids the hub may
   vend), set **`active: false`** until the endpoints verify.
2. Verify the JWKS is reachable and the token endpoint mints a conforming directed JWT (`iss`,
   `aud:"obi"`, `sub`, `iat`, `exp ≤ 60 min`, `business_id` + `source_system` + `target_system`).
3. Confirm the vend rights: the issuer may assert only the source ids agreed in step 1 (the target
   is never checked — ADR-source-system-decides-widget-eligibility).
4. Flip to **`active: true`** only after that passes.
5. Redeploy the backend (new registry entry) and rebuild/redeploy the frontend (the iframe's
   `frame-ancestors` CSP derives from the active embed domains).
6. Remove the temporary `obi-test` issuer and its embed allow-list entry once the real platforms
   are active.
7. Run the test matrix against the deployed origin and save the output where the plan says.

Entries go active only after verification, never on receipt of the email.

---

## Follow-up (2026-10-13) — focused fact requests

> **DRAFTS — the owner edits and sends these.** Both partners have shared partial information; neither
> is complete enough to activate (status + per-field gaps: `partner-facts.md`). These are short,
> targeted asks for the specific facts still missing, not the full contract again. JWKS approach:
> **Option A** below (their staging), while we verify our side on the local harness in parallel.
> Signer: Matisse.

### 3. Follow-up to Marien (Base)

**Subject:** Obi on Base — the five facts I still need to wire it up

Hi Marien,

Thanks for the earlier details. To register Base and start testing, I still need five things:

1. **Issuer** — the exact `iss` string your tokens will carry. (A hostname isn't the issuer, so I
   need the literal value.)
2. **JWKS URL** — a reachable HTTPS URL serving your public keys as JWKS, keyed by `kid`, signed
   **RS256 or ES256**. We fetch and cache it, so it needs to stay up.
3. **Embed origins** — the exact HTTPS origins where Obi will appear. You mentioned
   `app.omniboost.io` (live) and `base.development.omniboost.io` (dev) earlier — please confirm those
   are right for this integration, or send the correct ones. A missing origin blocks the embed.
4. **One example token** in the directed form — for one real customer, the canonical **source** id
   and **target** id (e.g. `source_system: "toast"`, `target_system: "mews"`), plus `business_id`
   and the user `sub`. Two separate ids, never a compound.
5. **Token endpoint** — the deployed URL that mints that token (the `tokenUrl` the page passes to
   `Obi.init`).

For testing before your production endpoints exist: if you can stand up a **staging** issuer + JWKS +
token endpoint, we verify against that. We'll be proving our own wiring on a local test harness in
the meantime, so we're ready the moment your staging is up.

One thing to settle on a call: you flagged that a single user can reach **multiple customers and
connections and switch without logging out**. Good news — the widget already handles that. When your
page re-fetches (or re-mints) the token for the newly-selected customer and hands it to Obi, Obi sees
the changed customer and starts a fresh chat, so nothing carries over between customers. What I'd like
to agree is the trigger on your side: which UI event re-fetches the token, and whether you'd rather
re-point the widget or just hand it the new token.

Embed against the **web** host — `https://obi-web-production.up.railway.app/obi.js` — not the backend
API host. It moves to a branded `obi.omniboost.com` before go-live, and the only change on your side
will be that one `src` line (with plenty of notice).

Send me the five and I'll add Base on our side and we test.

Best,
Matisse

### 4. Follow-up to Jasper (Data Hub)

**Subject:** Obi on Data Hub — the directed token, and the five facts I still need

Hi Jasper,

Thanks for the sample — I've kept it as a reference. It's a local, expired test token, so it doesn't
tell me staging is working yet; when staging is ready, please send a **fresh** one. To register Data
Hub I need five things:

1. **Staging issuer** — the real `iss`. The sample used `https://pos-pms-laravel.test`, which is a
   local fixture; I need the deployed staging value.
2. **Staging JWKS URL** — you proposed `https://<staging-domain>/.well-known/jwks.json`, which is
   exactly right; I just need the actual staging domain and the live URL (RS256 is fine).
3. **Embed origin** — the exact HTTPS staging origin where Obi will load. `www.datahub.be` showed up
   in our earlier example, but I don't want to assume it — confirm the real one.
4. **The directed pair** — one point to nail down. The sample carried `integration: "toast-opera"`.
   Our gate refuses a compound like that with a 401: it reads as two ids stuck together and resolves
   to nothing. Please send the two systems as **separate canonical ids with a direction** — e.g.
   `source_system: "toast"`, `target_system: "opera-cloud"` — and confirm which is the source and
   which is the target, per customer. A connection is directional: `toast → opera-cloud` is not the
   same as `opera-cloud → toast`.
5. **Token endpoint** — the deployed staging URL that mints the directed JWT (`iss`, `aud: "obi"`,
   `sub`, `iat`, `exp`, `business_id`, `source_system`, `target_system`).

From your sample I've got: RS256, `aud: obi`, 600 s lifetime (within our 60-minute cap), and customer
id `8` — which works as the `business_id`. Keep normal expiry checking on your side; I keep it on too.

For testing before production: standing up that staging issuer + JWKS + token endpoint is what unblocks
a real end-to-end test. We'll verify our own side on a local harness in parallel, so we're ready as
soon as your staging is up.

Embed against the **web** host — `https://obi-web-production.up.railway.app/obi.js` — not the backend
API host (an earlier thread gave the backend host; that's the chat API, not the script source). It
moves to `obi.omniboost.com` before go-live, one `src`-line change with notice.

Send the five and I'll wire Data Hub up and we test.

Best,
Matisse
