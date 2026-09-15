# Prompt: implement "Embedding Obi in another application" so we can start testing

You are an engineering agent working in the Omniboost monorepo (backend: Python/FastAPI under `apps/automation`; widget: Next.js under `apps/web`; contracts under `packages/contracts`). The design you are implementing is section 03.2 of `obi-rag-system-flow.html`, also written out in `obi-system-brief.md` (section 03.2 and the panels `em-loader`, `em-hostbackend`, `em-token`, `em-backend`, `em-kb`, `em-button`). Read those first. This prompt tells you what has to exist and what has to change so the flow can be tested end to end, first on our own pages, then with Mews, Toast and Opera Cloud.

## What the design is, in six lines

1. A platform (Mews, Toast, Opera Cloud, an Omniboost app) adds one script tag to its page: `obi.js`, served from our domain.
2. `obi.js` draws a round Obi button at the top of the screen and opens the chat window in an iframe from our domain when the button is clicked.
3. At that click, `obi.js` fetches a short signed note (a JWT) from an endpoint on the platform's own server. The note carries `iss`, `aud`, `sub`, `iat`, `exp`, and either all three business values (`company_id`, `company_name`, `integration`) or none of them.
4. `obi.js` hands the note to the frame by `postMessage`, keeps it in memory only, sends it as a bearer header with every question, renews it silently before it expires, and forgets it on `Obi.clear()`.
5. The Obi backend verifies the note (algorithm allow-list, signature by `kid`, `iss` against `platforms.json`, `aud = obi`, `exp`), then builds one `AuthContext` from the verified claims and uses it for every read.
6. The knowledge base filters by tags: `integration = mews` gives pages tagged `mews` or `general`; no values gives `general` only; an unknown integration is refused. Source and page permissions still apply.

## What exists today (do not rebuild it)

- The widget UI in `apps/web/src/features/chat/` and its proxy route in `apps/web/src/features/chat/server/route-handlers.ts`, which adds the host key (`CHAT_API_KEY`) and streams SSE back. Keep both. The one change: forward the user's bearer token.
- `_verify_api_key` in `rag_agent/server/router.py:254-267` (constant-time host key check). Keep it; the token check runs after it.
- `resolve_allowed_scopes` in `retrieval/domain/knowledge_scope.py` (integration plus `general`, in code). Replace with the map from `platforms.json`.
- Row security in Postgres (source policy live; scope policy in migration 0010, not yet applied to Supabase). Do not touch the policies for this work. Apply 0010 if it is not live yet.
- The pilot's shared invite token: `apps/web/src/features/chat/api/access-token.ts` (reads `?access_token=` from the URL into sessionStorage) and `apps/web/src/features/chat/server/auth.ts` (constant-time compare). Retire both.

## What to build, in this order

### 1 · Backend: accept and verify the note

- Add `config/platforms.json` with the shape below and a loader (`platform/config/platforms.py`) that validates it at startup: every tag under `integrations` must exist in `knowledge_scopes.json`; `general` is always included; `classified` never; a bad entry stops startup; an empty `platforms` object outside local stops startup.
- Add `rag_agent/server/token_verifier.py`. Verification order is fixed: read `iss` from the note and find its entry (no entry: 401); reject any algorithm not in the entry's list (`RS256`, `ES256`; never `HS256`); find the public key by `kid` from the entry's `jwks_url` (cache, refresh on unknown `kid`); check the signature; check `aud` contains `obi`; check `exp` with 60 s leeway and `iat` present; check `exp - iat` does not exceed the entry's `lifetime_minutes`. Any failure: 401 with no detail.
- Add `rag_agent/application/auth_context.py`. Build one frozen `AuthContext` from the verified claims: `company_id`, `company_name`, `integration`, `allowed_scopes` (from the map; `general` only when the three values are absent), `allowed_sources` (`confluence`), `principal` (None for embedded users until the identity mapping is decided), `space_id`, `token_subject`. An `integration` value not in the map: 401.
- Thread that one object through every read: search, rerank-text fetch, curated lookup, parent expansion (`retrieval/application/retriever.py`, `retrieval/infrastructure/search_repo.py`, `rag_agent/infrastructure/curated_knowledge_repo.py`). Both GUCs are set from it in every reader transaction. No read may run under looser rules than the search.
- Body rule: the body `knowledgeScope` is checked for shape and membership only. Unknown slug: 400 before any search. A known slug that disagrees with the note: ignored and logged. `principal` from the body is ignored.
- Rate limit key: the token subject; client IP only for requests without a token.
- `query_trace` gets a hash of `sub`, never the token or the raw subject.
- Settings: none of the old single-issuer variables. Everything per platform lives in `platforms.json`.

```json
{
  "platforms": {
    "mews":  { "issuer": "https://app.mews.com",     "jwks_url": "https://app.mews.com/.well-known/obi-jwks.json",     "domains": ["app.mews.com"],     "lifetime_minutes": 60, "algs": ["RS256", "ES256"] },
    "toast": { "issuer": "https://pos.toasttab.com", "jwks_url": "https://pos.toasttab.com/.well-known/obi-jwks.json", "domains": ["pos.toasttab.com"], "lifetime_minutes": 60, "algs": ["RS256", "ES256"] }
  },
  "integrations": {
    "mews":  ["mews", "general"],
    "toast": ["toast", "general"]
  }
}
```

### 2 · Frontend: the frame and the loader

- Add the frame page `apps/web/src/app/embed/page.tsx`: the round button, and the existing chat window when the button is clicked. Served with `Content-Security-Policy: frame-ancestors <every domain in platforms.json>`, built at request time; an empty list outside local returns 403.
- Add `apps/web/src/features/embed/loader.ts`, built to `public/obi.js`. Public API: `Obi.init({ tokenUrl })` and `Obi.clear()`. Behavior: inject the iframe; on the button click post `{type: "obi:open"}` to the frame and fetch `tokenUrl` (same-origin from inside the platform's page, so the platform's session cookie goes along and no CORS is needed); post `{type: "obi:token", token}` to the frame with the exact Obi origin as target (never `*`); set a timer to renew before `exp`; renew on the next activity after a long idle stretch; on a 401 from the backend renew once; on `Obi.clear()` post `{type: "obi:clear"}`.
- Add `apps/web/src/features/embed/iframe-bridge.ts` (the frame side): accept `obi:token` and `obi:clear` only from `window.parent` and only when `event.origin` is a domain in the platform's entry; keep the token in a variable (never a cookie, localStorage, sessionStorage or the URL); send `Authorization: Bearer <token>` on every `POST /api/chat`; on `obi:clear` drop the token, empty the thread, hide the company name, block sending until a new token arrives.
- Change the proxy to forward the `Authorization` header unchanged next to the host key. Delete the `access-token.ts` and `auth.ts` pilot path.
- Message types are exactly three: `obi:open`, `obi:token`, `obi:clear`.

### 3 · Contracts

- `packages/contracts/src/token-claims.json` (JSON schema for the note) and `packages/contracts/src/iframe-messages.ts` (the three message types). Add a drift test between the schema and the backend verifier.

### 4 · Test host pages on our own domain (this is what unblocks testing)

Build four pages under `apps/web/src/app/test-hosts/` that play the platform. Each page has its own note endpoint that signs with a test key, and each is a real entry in `platforms.json` (local and staging only):

| Page | Issuer entry | Note it hands out |
|---|---|---|
| `/test-hosts/none` | `test-mews` | no business values |
| `/test-hosts/mews` | `test-mews` | `company_id c_test_1`, `company_name Test Hotel`, `integration mews` |
| `/test-hosts/toast` | `test-toast` | `company_id c_test_2`, `company_name Test Restaurant`, `integration toast` |
| `/test-hosts/mews-2` | `test-mews` | `company_id c_test_3`, `company_name Second Hotel`, `integration mews` |

For each test issuer generate an RS256 key pair, keep the private key in the server environment, and serve the public key at `/.well-known/obi-jwks.json` for that issuer. Each page contains exactly the template a platform will paste: the script tag and `Obi.init({ tokenUrl: "/api/test-hosts/<name>/obi-token" })`. Use test pages tagged `mews`, `toast` and `general` in the Confluence test space so the answers differ by scope.

### 5 · Setup for Mews, Toast and Opera Cloud

Do this part too. For each of the three platforms:

- Add its entry to `platforms.json` (staging and production), with placeholders for `issuer` and `jwks_url` until the platform sends the real values. Mark the entry inactive until both are filled; the loader must skip inactive entries.
- Add its integration to the `integrations` map: `mews → [mews, general]`, `toast → [toast, general]`, `opera-cloud → [opera-cloud, general]`. Opera Cloud is still marked "Decision needed" on the page; add it behind the same inactive flag and make sure `opera-cloud` exists in `knowledge_scopes.json` before it goes live.
- Write the hand-over pack per platform in `docs/embedding/<platform>.md`: the script tag and init call with the platform's own `tokenUrl`; the note structure (default and with values) with the platform's issuer name filled in; the reference implementation of the note endpoint in Node and in Python (signed-in users only, three values from the platform's own records or none, RS256, `kid` in the header, lifetime as agreed); the four things we need back (issuer name, public key URL, domains, integration value); the done-when checks.
- Add a request checklist to each pack for their engineer: name a contact, give a test company for the integration and one test user in a restricted Confluence group.
- If anything on our side has to be configured for a platform to work (CSP domains, an inactive entry activated, a scope added, a staging URL for the frame), configure it now behind the inactive flag and document the one line that activates it.

### 6 · Decisions: use these defaults and flag them

Do not stop for these. Build to the default and list each one in your report as "built to default, awaiting confirmation".

| Decision | Default to build |
|---|---|
| Who signs the note | the platform's own server |
| Note lifetime | 60 minutes, per platform in `platforms.json` |
| When the note is fetched | at the button click, not at login |
| A note with no values | general pages only (not refused) |
| Per-person Confluence page permissions for embedded users | none; `principal` stays None, so open pages only |
| Company-specific content | none exists; no company rule yet |
| Which platform goes first | prepare all three packs; do not activate any entry |

## Done when

All seven pass on the four test host pages, in CI where possible and once by hand on staging:

1. All four test host pages load the button, open the chat, and get answers.
2. The `mews` page gets Mews and general pages and never a Toast-only page; the `toast` page the reverse.
3. The `none` page gets general pages only.
4. A note with one changed character, an expired note, or no note: 401 before any search; the frame asks for a new note exactly once.
5. A `postMessage` from a domain not in the platform's entry, or from a window that is not the parent: ignored, one log line, no token stored.
6. After an hour of use the chat still works and the log shows one silent renewal and no click.
7. After `Obi.clear()` the frame holds no note and no chat, and the next question is refused until a new note arrives.

Plus: the token never appears in a URL, a cookie, web storage, a server log line or the trace row (hash of `sub` only). No second backend and no knowledge base per integration were introduced.

## What to hand back

1. The pull requests, in the order above, each with its tests.
2. The final `platforms.json` for local, staging and production, with the three platform entries inactive.
3. The three hand-over packs in `docs/embedding/`.
4. A short report: every "Today" claim from the design that you found drifted from the code, every default you built to, and anything that blocked a done-when check.
