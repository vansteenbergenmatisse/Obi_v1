# Phase 11.1c — Embedding Obi in another application (iframe loader + JWT edge binding)

> **Status: SCOPED, not built (2026-09-12).** This is the design-of-record for the next feature.
> It is the **edge binding ADR-0014 explicitly deferred** ("does not add a per-user→customer binding at
> the edge … still one shared `CHAT_API_KEY` … that is 11.1c + the deferred AWS deploy"). The verified
> JWT `integration` claim replaces the caller-self-reported `knowledge_scope` — i.e. it closes the last
> *trusted-from-caller* gap on the scope axis, on top of the DB backstop already built in 11.1a.
>
> Governing docs: this spec + [ADR-0014](../adr/0014-Customer-Scope-Isolation-Backstop.md). Ledger:
> `docs/rag/PLAN.md` §0. Per-platform hand-over packs live beside this file in `docs/embedding/`.

## ⚠️ Reconciliation notes (read before building — resolves drift in the source prompt)

1. **Referenced design files are NOT in the repo.** The source prompt says to read section 03.2 of
   `obi-rag-system-flow.html` and `obi-system-brief.md`. Neither exists in the tree (checked 2026-09-12).
   Drop them in `docs/` if they should be the visual source of truth; until then, **this file is the
   spec**.
2. **CRITICAL — scope-slug drift.** The prompt's `platforms.json`/`integrations` examples use bare tags
   (`mews`, `toast`, `general`, `opera-cloud`). The **live recognized set** in
   `config/knowledge_scopes.json` is `obi-general-test`, `obi-mews-test`, `obi-operacloud-test`,
   `obi-toast-test`. The prompt's own startup rule — "every tag under `integrations` must exist in
   `knowledge_scopes.json`" — would **reject the example config as written**. **Decision needed** (see
   Decisions table): either (a) the `integrations` map targets the real `obi-*-test` slugs, or (b) the
   scopes are renamed back to bare names. Default assumption for the build: **(a)** — keep the live
   slugs, so `integrations` = `{"mews": ["obi-mews-test","obi-general-test"], ...}` and the *platform
   key* (`mews`) is the wire value in the JWT `integration` claim, mapped to slugs by the config. This
   keeps the JWT surface human-friendly while respecting the live tag vocabulary. Confirm before coding.
3. **Migration `0010` is a prerequisite for staged/prod testing.** The DB scope-isolation backstop
   (`0010_customer_scope_rls`) exists in code but is **not applied to live Supabase** (live head `0009`).
   Local docker testing works without it; the isolation done-when checks (#2/#3) are only *hard-enforced*
   once `0010` is live. Apply it as part of this phase's ops (operator step).
4. **`principal` stays `None` for embedded users (v1 decision, confirmed 2026-09-11).** Integration-level
   content scoping only; no per-person Confluence page ACL in v1. Open pages only for embedded users.

---

## What the design is, in six lines

1. A platform (Mews, Toast, Opera Cloud, an Omniboost app) adds one script tag: `obi.js`, from our domain.
2. `obi.js` draws a round Obi button at the top of the screen and opens the chat window in an iframe from
   our domain when the button is clicked.
3. At that click, `obi.js` fetches a short signed note (a JWT) from an endpoint on the platform's own
   server. The note carries `iss`, `aud`, `sub`, `iat`, `exp`, and either all three business values
   (`company_id`, `company_name`, `integration`) or none.
4. `obi.js` hands the note to the frame by `postMessage`, keeps it in memory only, sends it as a bearer
   header with every question, renews it silently before it expires, and forgets it on `Obi.clear()`.
5. The Obi backend verifies the note (algorithm allow-list, signature by `kid`, `iss` against
   `platforms.json`, `aud = obi`, `exp`), builds one `AuthContext` from the verified claims, and uses it
   for every read.
6. The knowledge base filters by tags: `integration = mews` → pages tagged `mews`(→`obi-mews-test`) or
   `general`(→`obi-general-test`); no values → `general` only; unknown integration → refused. Source and
   page permissions still apply.

## What exists today (do not rebuild it)

- Widget UI `apps/web/src/features/chat/` + proxy `apps/web/src/features/chat/server/route-handlers.ts`
  (adds host key `CHAT_API_KEY`, streams SSE back). Keep both. One change: forward the user bearer token.
- `_verify_api_key` in `rag_agent/server/router.py:254-267` (constant-time host-key check). Keep it; the
  token check runs after it.
- `resolve_allowed_scopes` in `retrieval/domain/knowledge_scope.py` (integration + `general`, in code).
  Replace with the map from `platforms.json`.
- Row security in Postgres (source policy live; scope policy `0010` in code, **not yet live on Supabase**).
  Do not touch the policies. Apply `0010` if it is not live yet.
- Pilot shared invite token: `apps/web/src/features/chat/api/access-token.ts` (`?access_token=` →
  sessionStorage) + `apps/web/src/features/chat/server/auth.ts` (constant-time compare). **Retire both.**

## What to build, in this order

### 1 · Backend: accept and verify the note
- `config/platforms.json` + loader `platform/config/platforms.py`, validated at startup: every tag under
  `integrations` exists in `knowledge_scopes.json`; `general`/`obi-general-test` always included;
  `classified` never; bad entry stops startup; empty `platforms` outside local stops startup.
- `rag_agent/server/token_verifier.py`. Fixed verification order: read `iss` → find entry (none → 401);
  reject any alg not in the entry list (`RS256`, `ES256`; never `HS256`); find key by `kid` from the
  entry `jwks_url` (cache, refresh on unknown `kid`); check signature; `aud` contains `obi`; `exp` with
  60 s leeway + `iat` present; `exp - iat` ≤ entry `lifetime_minutes`. Any failure → 401, no detail.
- `rag_agent/application/auth_context.py`. Frozen `AuthContext` from verified claims: `company_id`,
  `company_name`, `integration`, `allowed_scopes` (from the map; general-only when the three values
  absent), `allowed_sources` (`confluence:default`), `principal` (None for embedded users),
  `space_id`, `token_subject`. An `integration` not in the map → 401.
- Thread that one object through every read: search, rerank-text fetch, curated lookup, parent expansion
  (`retrieval/application/retriever.py`, `retrieval/infrastructure/search_repo.py`,
  `rag_agent/infrastructure/curated_knowledge_repo.py`). Both GUCs set from it in every reader txn. No
  read runs under looser rules than the search.
- Body rule: body `knowledgeScope` checked for shape + membership only. Unknown slug → 400 before search.
  Known slug disagreeing with the note → ignored + logged. Body `principal` ignored.
- Rate-limit key: the token subject; client IP only for tokenless requests.
- `query_trace` gets a **hash of `sub`**, never the token or the raw subject.
- Settings: none of the old single-issuer variables. Per-platform config lives in `platforms.json`.

```json
{
  "platforms": {
    "mews":  { "issuer": "https://app.mews.com",     "jwks_url": "https://app.mews.com/.well-known/obi-jwks.json",     "domains": ["app.mews.com"],     "lifetime_minutes": 60, "algs": ["RS256", "ES256"] },
    "toast": { "issuer": "https://pos.toasttab.com", "jwks_url": "https://pos.toasttab.com/.well-known/obi-jwks.json", "domains": ["pos.toasttab.com"], "lifetime_minutes": 60, "algs": ["RS256", "ES256"] }
  },
  "integrations": {
    "mews":  ["obi-mews-test", "obi-general-test"],
    "toast": ["obi-toast-test", "obi-general-test"]
  }
}
```
> NOTE the `integrations` values use the **live `obi-*-test` slugs** per reconciliation note #2, not the
> bare tags in the source prompt. Confirm this mapping before coding.

### 2 · Frontend: the frame and the loader
- Frame page `apps/web/src/app/embed/page.tsx`: round button + existing chat window on click. Served with
  `Content-Security-Policy: frame-ancestors <every active domain in platforms.json>`, built at request
  time; empty list outside local → 403.
- `apps/web/src/features/embed/loader.ts` → built to `public/obi.js`. API: `Obi.init({ tokenUrl })`,
  `Obi.clear()`. Inject the iframe; on button click post `{type:"obi:open"}` and fetch `tokenUrl`
  (same-origin from the platform page → session cookie rides, no CORS); post `{type:"obi:token", token}`
  with the exact Obi origin as target (never `*`); timer to renew before `exp`; renew on next activity
  after long idle; on backend 401 renew once; on `Obi.clear()` post `{type:"obi:clear"}`.
- `apps/web/src/features/embed/iframe-bridge.ts` (frame side): accept `obi:token`/`obi:clear` only from
  `window.parent` and only when `event.origin` ∈ the platform entry domains; keep the token in a variable
  (never cookie/localStorage/sessionStorage/URL); send `Authorization: Bearer <token>` on every
  `POST /api/chat`; on `obi:clear` drop token, empty thread, hide company name, block send until a new
  token arrives.
- Proxy forwards the `Authorization` header unchanged next to the host key. Delete `access-token.ts` +
  `auth.ts` pilot path.
- Message types are exactly three: `obi:open`, `obi:token`, `obi:clear`.

### 3 · Contracts
- `packages/contracts/src/token-claims.json` (JSON schema for the note) +
  `packages/contracts/src/iframe-messages.ts` (the three message types). Drift test between schema and
  the backend verifier.

### 4 · Test host pages on our own domain (this unblocks testing)
**Operator-confirmed set (2026-09-12):** four pages under `apps/web/src/app/test-hosts/` — `none`,
`mews`, `toast`, `opera-cloud` (the operator swapped the spec's `mews-2` for `opera-cloud` to get
three-way integration isolation). Each has its own note endpoint signing with a test key, and is a real
entry in `platforms.json` (local + staging only):

| Page | Issuer entry | Note |
|---|---|---|
| `/test-hosts/none`        | `test-mews`  | no business values |
| `/test-hosts/mews`        | `test-mews`  | `company_id c_test_1`, `company_name Test Hotel`, `integration mews` |
| `/test-hosts/toast`       | `test-toast` | `company_id c_test_2`, `company_name Test Restaurant`, `integration toast` |
| `/test-hosts/opera-cloud` | `test-opera` | `company_id c_test_3`, `company_name Test Resort`, `integration opera-cloud` |

Per test issuer (`test-mews`, `test-toast`, `test-opera`): generate an RS256 key pair, private key in the
server env, public key at that issuer's `/.well-known/obi-jwks.json`. Each page contains exactly the paste
template: the script tag + `Obi.init({ tokenUrl: "/api/test-hosts/<name>/obi-token" })`.

**Confluence content: REUSE the existing four live `obi-*-test` pages** (operator-confirmed — no new
content needed): `General Obi information` (`obi-general-test`), `Mews Testpage` (`obi-mews-test`,
"bananas"), `Toast Testpage` (`obi-toast-test`, "grapes"), `Opera Cloud Testpage` (`obi-operacloud-test`,
"apples"). Answers already differ by scope, so the isolation done-when checks work as-is.

**Dropped-proof note:** removing `mews-2` loses the "same integration, different `company_id` → identical
content, `company_id` is audit-only" assertion at the browser level. Cover it with a **backend unit test**
on `AuthContext` instead (two claims sets differing only in `company_id` → identical `allowed_scopes`).

### 5 · Setup for Mews, Toast and Opera Cloud
Per platform: add its entry to `platforms.json` (staging + prod) with placeholder `issuer`/`jwks_url`,
**marked inactive** until both are filled (loader skips inactive entries); add its integration to the map
(`mews→[obi-mews-test,obi-general-test]`, `toast→[obi-toast-test,obi-general-test]`,
`opera-cloud→[obi-operacloud-test,obi-general-test]`; Opera Cloud behind the inactive flag, ensure
`obi-operacloud-test` exists before go-live — it does); write the hand-over pack
`docs/embedding/<platform>.md` (script tag + init with the platform's `tokenUrl`; note structure default
+ with-values; reference note endpoint in Node **and** Python — signed-in users only, three values or
none, RS256, `kid` in header, agreed lifetime; the four things we need back; done-when checks); add a
request checklist (contact, test company per integration, one test user in a restricted Confluence
group); configure anything on our side behind the inactive flag and document the one line that activates.

### 6 · Decisions (build to default, flag in report)
| Decision | Default |
|---|---|
| Who signs the note | the platform's own server |
| Note lifetime | 60 min, per platform in `platforms.json` |
| When the note is fetched | at button click, not login |
| A note with no values | general only (not refused) |
| Per-person Confluence page perms | none; `principal` stays None → open pages only |
| Company-specific content | none exists; no company rule yet |
| Which platform first | prepare all three packs; activate none |
| **Scope-slug mapping (drift #2)** | **`integrations` targets `obi-*-test` slugs; platform key is the JWT `integration` wire value** — confirm |

## Done when
1. All four test host pages (`none`, `mews`, `toast`, `opera-cloud`) load the button, open the chat, get
   answers.
2. `mews` page → Mews + general, never Toast-only or Opera-only; `toast` and `opera-cloud` pages → the
   equivalent, each seeing only its own integration + general (three-way isolation).
3. `none` page → general only.
3a. Backend unit test: two claim sets differing only in `company_id` → identical `allowed_scopes`
    (replaces the dropped `mews-2` browser proof).
4. One changed char / expired / missing note → 401 before any search; frame asks for a new note exactly
   once.
5. `postMessage` from a domain not in the entry, or a non-parent window → ignored, one log line, no token
   stored.
6. After an hour: chat still works; log shows one silent renewal, no click.
7. After `Obi.clear()`: frame holds no note and no chat; next question refused until a new note arrives.
- Token never in URL/cookie/web-storage/server-log/trace row (hash of `sub` only). No second backend, no
  per-integration knowledge base.

## Hand back
1. PRs in the order above, each with tests.
2. Final `platforms.json` for local/staging/prod, three platform entries inactive.
3. Three hand-over packs in `docs/embedding/`.
4. Short report: every drifted "Today" claim, every default built to, anything that blocked a done-when.
