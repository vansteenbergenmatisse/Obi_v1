# widget

## Purpose (two lines)
`apps/web` is the Next.js widget: the chat UI (launcher, teaser, panel, composer, six locales), the `/api/chat` proxy route that injects the backend's server key and streams the SSE answer back, and the `/embed` iframe frame + `obi.js` host-page loader that lets a third-party platform embed Obi with a per-user signed token.
It never decides access, never holds a signing key for the backend's own auth, and never opens a database connection — the backend (`apps/automation`) owns all of that.

## Entry points

| symbol | file:line | called by |
|---|---|---|
| `POST` → `handlePostChat` | `apps/web/src/app/api/chat/route.ts:8-10` | Next.js router (widget's own browser `fetch`) |
| `PATCH` → `handlePatchFeedback` | `apps/web/src/app/api/chat/[traceId]/feedback/route.ts:10-16` | Next.js router |
| `GET` → active domains | `apps/web/src/app/api/internal/active-domains/route.ts:10-12` | `middleware.ts:30` (internal fetch, Edge can't call `node:fs`) |
| `middleware(request)` | `apps/web/src/middleware.ts:27-49` (matcher `/embed`) | Next.js Edge runtime on every `/embed` request |
| `EmbedPage` (default export) | `apps/web/src/app/embed/page.tsx:22-25` | Next.js router for `/embed` |
| `EmbedFrame` | `apps/web/src/app/embed/embed-frame.tsx:26-48` | `EmbedPage` |
| `HomePage` (default export) | `apps/web/src/app/(site)/page.tsx:24-60` | Next.js router for `/` |
| `RootLayout` (mounts `ChatSessionProvider`+`ChatWidget`) | `apps/web/src/app/(site)/layout.tsx:21-36` | Next.js, `(site)` route group |
| `GET` → test-host token mint | `apps/web/src/app/api/test-hosts/[name]/obi-token/route.ts:12-40` | `obi.js`'s `fetchAndSendToken` via `tokenUrlFor` |
| `GET` → test-host JWKS | `apps/web/src/app/api/test-hosts/jwks/[issuer]/route.ts:13-34` | a JWT verifier resolving `jwks_url` (backend, in dev/local) |
| `window.Obi.init/.clear/.destroy` | `apps/web/src/features/embed/loader.ts:191-232` | one `<script>` tag on the host page (bundled to `public/obi.js`) |
| `initIframeBridge` | `apps/web/src/features/embed/iframe-bridge.ts:40-73` | `apps/web/src/app/embed/embed-frame.tsx:30` |

## Reads and writes

| tables, files, queues touched | read or write | file:line |
|---|---|---|
| `config/knowledge_scopes.json` (repo root) | read (by a drift **test**, not the app itself) | `apps/web/src/features/chat/tests/knowledge-scopes.test.ts:18,26` |
| `config/platforms.json` / `config/platforms.local.json` (repo root, `node:fs`) | read | `apps/web/src/features/embed/platforms.ts:29,44-46,54` |
| `process.env.CHAT_API_KEY`, `AUTOMATION_API_BASE_URL`, `AUTOMATION_API_TIMEOUT_MS` | read | `apps/web/src/platform/automation-api/client.ts:24,28-30` |
| `process.env.TEST_OBI_PRIVATE_KEY_*` / `TEST_OBI_PUBLIC_KEY_*` (local test-host only, gitignored) | read | `apps/web/src/app/api/test-hosts/[name]/obi-token/route.ts:22`; `.../jwks/[issuer]/route.ts:23` |
| `public/obi.js` | write (build-time esbuild output, not runtime) | `apps/web/package.json:9` |
| No database, no queue | — | not present anywhere under `apps/web/src` (confirmed by inspection; matches `sc-frontend`'s "never opens a database connection") |

## External calls

| client | endpoint | timeout, retry, breaker present? | file:line |
|---|---|---|---|
| `callAutomationApi` | `POST {AUTOMATION_API_BASE_URL}/chat` | `AbortSignal.timeout(config.timeoutMs)`; no retry (documented as deliberate — retrying a state-mutating POST is unsafe without idempotency); no breaker | `apps/web/src/platform/automation-api/client.ts:51-71` |
| `callAutomationApi` (feedback) | `PATCH {base}/chat/{traceId}/feedback` | timeout overridden to `FEEDBACK_TIMEOUT_MS=15_000`ms; no retry | `apps/web/src/features/chat/server/route-handlers.ts:82,213-222` |
| `middleware` → internal fetch | `GET /api/internal/active-domains` (same-origin) | no explicit timeout/retry; a failed fetch is treated as "no active domains" → fails toward 403, never allow-all | `apps/web/src/middleware.ts:29-41` |
| `obi.js` → `fetchAndSendToken` | `GET {tokenUrl}` (host page's own origin, `credentials: "same-origin"`) | no `AbortSignal` timeout; exactly one retry on a 401 from the host's own minting endpoint | `apps/web/src/features/embed/loader.ts:93-120` |
| Browser `chat-client` | `POST /api/chat` (SSE) | no client-side timeout beyond a caller-supplied `AbortSignal`; no retry | `apps/web/src/features/chat/api/chat-client.ts:80-101` |

## Tests present

| test file | behaviors asserted | panel ids |
|---|---|---|
| `apps/web/src/features/chat/tests/route-handlers.test.ts` | malformed JSON rejected, `knowledgeScope` forwarded as `knowledge_scope`, streaming passthrough | `w-proxy`, `r1-proxy` |
| `apps/web/src/features/chat/tests/validation.test.ts` | shape-only checks, history-ends-on-user rule | `w-proxy` |
| `apps/web/src/features/chat/tests/chat-client.test.ts` | SSE parsing, `Authorization` header from `getToken()` | `w-render`, `w-token` |
| `apps/web/src/features/chat/tests/knowledge-scopes.test.ts` | widget list mirrors `config/knowledge_scopes.json` in order; `obi-general-test` always present | `cm-config`, `tg-config`, `ks-validate` |
| `apps/web/src/features/chat/tests/chat-session-provider.test.tsx` | `knowledgeScope` sent/omitted correctly on outgoing request | `w-scope` |
| `apps/web/src/features/chat/tests/composer.test.tsx`, `attachment-strip.test.tsx` | attachment staging/removal | `w-composer` |
| `apps/web/src/features/chat/tests/chat-launcher.test.tsx`, `teaser-popup.test.tsx`, `use-widget-visibility.test.tsx` | 3 s/20 s teaser timing, pulsing state | `w-launcher` |
| `apps/web/src/features/chat/tests/message-bubble.test.tsx`, `message-list.test.tsx` | citation chips, refusal banner, clarifying chips render | `w-render`, `r4-refuse` |
| `apps/web/src/features/chat/tests/scope-menu.test.tsx`, `panel-header.test.tsx` | dev scope switcher gated on `NEXT_PUBLIC_SHOW_SCOPE_SWITCHER` | `w-scope` |
| `apps/web/src/features/chat/tests/panel-body.test.tsx` | screenshot capture hides `[data-obi-widget-root]` | `w-screenshot` |
| `apps/web/src/features/embed/tests/iframe-bridge.test.ts` | parent-only + origin allow-list, memory-only token, `obi:token`/`obi:clear`/`obi:open` | `em-button`, `s-edge` |
| `apps/web/src/features/embed/tests/loader.test.ts` | one iframe injected, exact-origin `postMessage` (never `"*"`), silent renewal before `exp`, one 401 retry, idempotent re-init | `em-loader` |
| `apps/web/src/features/embed/tests/frame-csp.test.ts` | `frame-ancestors` never `"*"`, 403 outside local/dev with no active domains, fails closed on fetch error | `em-button`, `s-edge` |
| `apps/web/src/app/test-hosts/multi-user-content.test.tsx`, `test-host-content.test.tsx` | multi-user switcher re-points `Obi.init` per user | `sc-user`, `ov-auth` |

## Known gaps

- No client-side image-size check exists in the composer — only the 4-per-turn count is enforced (`MAX_ATTACHMENTS`); the "5 MB each" cap is documented as backend-only in a comment, not code, in this app — `apps/web/src/features/chat/ui/composer.tsx:38-110` (no size check); `apps/web/src/features/chat/server/route-handlers.ts:74-80` (docstring reference to the backend's cap only).
- `model/knowledge-scopes.ts` is a hand-mirrored copy guarded by a Vitest drift test, not a build-time code-generation step, despite four design panels (`cm-config`, `tg-config`, `sc-frontend`, `ks-deploy`) describing it as "generated from the JSON at build time" / "no hand-written copy, no drift test" — `apps/web/src/features/chat/model/knowledge-scopes.ts:5-11`; `apps/web/src/features/chat/tests/knowledge-scopes.test.ts:4-9`.
- Widespread code comments cite "PLAN 11.1c, ADR-0014" as the authority for retiring the pilot invite-token and building the per-user JWT/embed handshake (e.g. `apps/web/src/features/chat/server/route-handlers.ts:12`; `apps/web/src/features/embed/iframe-bridge.ts:2`; `apps/web/src/features/embed/loader.ts:4`; `apps/web/src/app/embed/embed-frame.tsx:6`; `apps/web/src/app/api/test-hosts/config.ts:5`), but `docs/adr/0014-Customer-Scope-Isolation-Backstop.md:1-5` is a different, backend-only ADR (DB-level RLS scope isolation in `apps/automation`) — the citation is either mislabeled or points at a renumbered/undated ADR not present under that number. Flagged, not resolved (ambiguous — needs owner confirmation, not a guess).
- The real `/embed` frame derives `knowledgeScope` entirely from the verified token server-side and never takes a `knowledgeScope` prop (`apps/web/src/app/embed/embed-frame.tsx:5-6,26-48`), while `apps/web/src/features/chat/ui/scope-menu.tsx` and the `ChatSessionProvider`'s `knowledgeScope` prop path are exercised only by the dev switcher and tests — no first-class embedding page in this repo actually sets the prop today.
- All three real platform entries in `config/platforms.json:4-6` are `active: false`; only the local test-host RS256 issuer scaffolding (`apps/web/src/app/api/test-hosts/**`) proves the per-user JWT flow end to end today.

## Claims from the design

| panel | claim | file:line | verdict | note |
|---|---|---|---|---|
| ov-widget | "Built in apps/web. Launcher, teaser, panel, composer, images, screenshot, six locales, dev-only scope switcher." | `apps/web/src/features/chat/ui/chat-launcher.tsx`, `teaser-popup.tsx`, `panel-body.tsx`, `composer.tsx`, `model/i18n.ts:13`, `panel-header.tsx:52` | confirmed | all present |
| ov-widget | "Shared invite token for the pilot." | `apps/web/src/features/chat/server/route-handlers.ts:12-14` | drifted | the pilot invite token (`WIDGET_ACCESS_TOKEN`/`access-token.ts`/`auth.ts`) was deleted per ADR-cited PLAN 11.1c; replaced by per-user JWT forwarding |
| ov-widget | "The widget calls its own proxy route." | `apps/web/src/features/chat/api/chat-client.ts:87` | confirmed | |
| ov-widget | "The proxy adds the server key and streams the answer back." | `apps/web/src/platform/automation-api/client.ts:57,65-70`; `apps/web/src/features/chat/server/route-handlers.ts:181-188` | confirmed | |
| ov-auth | "Today: Does not exist. A shared invite token gates the pilot widget…" | `apps/web/src/app/api/test-hosts/[name]/obi-token/route.ts:30-37` | drifted | a real per-user RS256 JWT flow (iss/aud/sub/iat/exp/company_id/company_name/integration) is built and live-proven for test hosts (git `59385f4`); not yet wired to a real platform (`config/platforms.json:4-6` all `active:false`) |
| ov-auth | Step 3-4: host page loads iframe, sends token by postMessage to exact Obi origin; iframe holds token in memory | `apps/web/src/features/embed/loader.ts:76-78,117-119`; `apps/web/src/features/embed/iframe-bridge.ts:27,55-58` | confirmed | never `"*"` target origin (tested `loader.test.ts:118-120`) |
| ov-auth | Step 5: backend verifies alg/sig/issuer/aud/expiry | (backend: `rag_agent/server/router.py`) | missing | owned by `apps/automation`, not `apps/web` |
| cm-web | `src/features/chat/ui/` — launcher, teaser, panel, composer, bubbles, menus | `apps/web/src/features/chat/ui/*.tsx` | confirmed | |
| cm-web | `src/features/chat/api/chat-client.ts` — SSE parsing | `apps/web/src/features/chat/api/chat-client.ts:103-123` | confirmed | |
| cm-web | `src/features/chat/server/route-handlers.ts, validation.ts, auth.ts` — the proxy | `apps/web/src/features/chat/server/route-handlers.ts:12-14` | drifted | `auth.ts` does not exist — deleted; only `route-handlers.ts` and `validation.ts` remain |
| cm-web | `src/features/chat/model/` — messages, i18n, knowledge-scopes | `apps/web/src/features/chat/model/{messages,i18n,knowledge-scopes}.ts` | confirmed | |
| cm-web | `src/app/api/chat/route.ts` — thin route entry | `apps/web/src/app/api/chat/route.ts:8-10` | confirmed | |
| cm-web | `src/features/embed/` — iframe bridge, token store (planned, section 03.2) | `apps/web/src/features/embed/{iframe-bridge,loader,csp,platforms,index}.ts` | drifted | not "planned" — built and unit-tested |
| cm-config | Widget scope list "generated from the JSON at build time (no hand-written copy, no drift test)" | `apps/web/src/features/chat/model/knowledge-scopes.ts:5-11`; `apps/web/src/features/chat/tests/knowledge-scopes.test.ts:4-9` | drifted | it IS a hand-written copy, guarded by a runtime/test-time drift check, not a build-time generator |
| cm-contracts | "Planned | token-claims.json … and iframe-messages.ts (obi:open, obi:token, obi:clear)" | `packages/contracts/src/token-claims.json:1-24`; `packages/contracts/src/iframe-messages.ts:1-33` | drifted | both already exist and are exported from `packages/contracts/src/index.ts:240-247` |
| cm-tokens | "light theme, indigo accent, Inter" | `packages/design-tokens/src/tokens.ts:8-31` (`accent: "#635bff"`) | confirmed | |
| w-launcher | Teaser 3 s initial / 20 s repeat; opens from launcher or teaser | `apps/web/src/features/chat/ui/use-widget-visibility.ts:14-15`; `chat-widget.tsx:33-38` | confirmed | |
| w-panel | Layout `clamp(360px,29%,440px)`; parts header/contour/message-list/composer; one `ChatSessionProvider` | `apps/web/src/features/chat/ui/floating-frame.tsx:22`; `panel-body.tsx:14-19`; `apps/web/src/app/(site)/layout.tsx:29-33` | confirmed | note: the `/embed` route mounts a **second**, separate `ChatSessionProvider` instance in `embed-frame.tsx:40`, each "mounted once" within its own root layout |
| w-composer | "Images: base64 on newest turn only, 4 per turn, 5 MB each" | `apps/web/src/features/chat/ui/composer.tsx:38,40-58` | drifted | 4-per-turn and base64 confirmed; the "5 MB each" cap is not enforced anywhere in `apps/web` — no size check exists in `composer.tsx`/`attachment-strip.tsx` |
| w-composer | "Empty text plus image allowed" | `apps/web/src/features/chat/ui/composer.tsx:144-163` | confirmed | |
| w-scope | "Set once, by the embedding page, as the knowledgeScope prop" | `apps/web/src/app/embed/embed-frame.tsx:5-6,26-48` | drifted | the real `/embed` frame explicitly passes **no** `knowledgeScope` prop; scope is derived server-side from the verified token instead |
| w-scope | "Sent on every request as knowledgeScope" | `apps/web/src/features/chat/ui/chat-session-provider.tsx:138` | confirmed | |
| w-scope | "Dev switcher behind NEXT_PUBLIC_SHOW_SCOPE_SWITCHER=true; never rendered in real embeds" | `apps/web/src/features/chat/ui/panel-header.tsx:52,120,212` | confirmed | |
| w-token | "Today: shared invite token, ?access_token=, sessionStorage, x-widget-access-token" | `apps/web/src/features/chat/server/route-handlers.ts:12-14` | missing | mechanism deleted |
| w-token | "Target: JWT per user via postMessage, held in memory, forwarded as bearer" | `apps/web/src/features/embed/iframe-bridge.ts:27`; `apps/web/src/features/chat/api/chat-client.ts:23,29-32`; `apps/web/src/features/chat/server/route-handlers.ts:61-71` | confirmed | already built, ahead of its "build" status label |
| w-token | Code location `features/chat/api/access-token.ts` | n/a | missing | file does not exist (deleted) |
| w-token | Code location `features/chat/server/auth.ts` | n/a | missing | file does not exist (deleted) |
| w-proxy | Path `/api/chat` and `/api/chat/{traceId}/feedback`; adds server key; structural checks only; byte passthrough | `apps/web/src/app/api/chat/route.ts:10`; `apps/web/src/app/api/chat/[traceId]/feedback/route.ts:10-16`; `apps/web/src/platform/automation-api/client.ts:57`; `apps/web/src/features/chat/server/validation.ts`; `route-handlers.ts:181-188` | confirmed | |
| w-i18n | Six locales covering greeting, chips, placeholder, footer, teaser, menus | `apps/web/src/features/chat/model/i18n.ts:13,25-57` | confirmed | |
| w-render | Tokens appended streaming; citation chips w/ unavailable-span fallback; refusal red banner + handoff + thumbs; clarifying banner + option chips; image labeled block | `apps/web/src/features/chat/ui/chat-session-provider.tsx:143-146`; `message-bubble.tsx:147-154,60-69,97-132,197-223,225-267` | confirmed | |
| w-render | "Partial (target): an amber note listing the uncovered parts" | `apps/web/src/features/chat/model/messages.ts` (no `partial`/`missingParts` field); `message-bubble.tsx` (no such element) | missing | matches design's own "target"/not-yet-built status |
| w-screenshot | html-to-image; hides `[data-obi-widget-root]`; lands in attachment strip | `apps/web/src/features/chat/ui/panel-body.tsx:37-65`; `floating-frame.tsx:18-21` | confirmed | |
| r1-proxy | `POST /api/chat`; `Authorization: Bearer CHAT_API_KEY`; SSE unbuffered; 30 MB body cap | `apps/web/src/features/chat/api/chat-client.ts:87`; `apps/web/src/platform/automation-api/client.ts:57`; `apps/web/src/features/chat/server/route-handlers.ts:81,181-188` | confirmed | |
| r1-proxy | "Its own auth: x-widget-access-token today; the user token in the target" | `apps/web/src/features/chat/server/route-handlers.ts:12-23,61-71` | drifted | `x-widget-access-token` no longer exists; the "target" (`X-Obi-Token` forwarding) is already implemented today |
| r1-auth | `_verify_api_key` in `rag_agent/server/router.py:254-267` | n/a in `apps/web` | missing | owned by `apps/automation` backend |
| r4-refuse | Widget shows red banner + contact link | `apps/web/src/features/chat/ui/message-bubble.tsx:147-154,71-92` | confirmed | reason taxonomy/logging itself (`refusal.py`) is backend-owned, missing here |
| r5-partial | "Answer.partial=true, missing_parts…" / widget amber note | `packages/contracts/src/index.ts:127-178` (no such fields); `message-bubble.tsx` (no such element) | missing | consistent with the panel's own "build" (not yet built) status; backend-owned when built |
| r5-stream | "Format: data: {json} blank line" | `apps/web/src/features/chat/api/chat-client.ts:113-118` | confirmed | rest of the panel (trace row, replay pacing) is backend-owned, missing here |
| r5-ground | Semantic support verification (judge model, batched) | n/a | missing | fully backend, owned by `apps/automation` (`rag_agent/domain/support.py`, proposed) |
| tg-first | Build creates document/version/chunks, label activation | n/a | missing | fully backend, owned by `apps/automation` ingestion |
| tg-config | "Also read by the widget build, which imports the JSON and generates its scope list without classified" | `apps/web/src/features/chat/model/knowledge-scopes.ts:5-11`; `config/knowledge_scopes.json:3-8` | drifted | same hand-mirror/test issue as `cm-config`; also `classified` is not present in the current JSON at all, so "without classified" does not yet apply |
| ks-validate | Startup validation (lowercase, unique, reserved `classified`) | n/a | missing | backend-only startup check, owned by `apps/automation` (`platform/config/knowledge_scopes.py`) |
| ks-deploy | "The widget build imports the same file and generates its scope list, without classified" | `apps/web/src/features/chat/model/knowledge-scopes.ts:5-11` | drifted | same as `cm-config`/`tg-config` |
| ks-widget | "The embed config sets knowledgeScope to the slug" | `apps/web/src/app/embed/embed-frame.tsx:5-6,26-48`; `apps/web/src/app/test-hosts/test-host-content.tsx:27-51` (no `knowledgeScope` anywhere in the paste template) | drifted | the real embed path never sets a scope from embed config — it comes from the verified token; the prop exists only for the dev switcher/tests |
| ks-remove | Removing a tag from the file | n/a | missing | backend + config workflow claim, not a code path in `apps/web` |
| s-edge | "apps/web/src/features/chat/server/auth.ts — the proxy check today" | `apps/web/src/features/chat/server/route-handlers.ts:12-14` | missing | file does not exist (deleted) |
| s-edge | `_verify_api_key` in `rag_agent/server/router.py:254-267` | n/a | missing | owned by `apps/automation` |
| sc-frontend | "Today: apps/web… Embedded in a platform page with a scope from its config. A shared pilot token gates it." | `apps/web/src/features/chat/server/route-handlers.ts:12-14`; `apps/web/src/app/embed/embed-frame.tsx:5-6` | drifted | pilot token retired; scope-from-embed-config model retired for the real `/embed` route |
| sc-frontend | "Owns … the iframe bridge (planned), the token in memory (planned)" | `apps/web/src/features/embed/iframe-bridge.ts:27`; `apps/web/src/features/chat/api/chat-client.ts:23,29-32` | drifted | both already built and tested, not "planned" |
| sc-frontend | "Talks to the backend only, over HTTPS POST /chat with SSE back" | `apps/web/src/platform/automation-api/client.ts:65-70` | confirmed | |
| sc-frontend | "Never decides access, holds a signing key, opens a database connection" | (absence confirmed by inspection across `apps/web/src`) | confirmed | |
| sc-user | Example Mews user, company/integration/principal shape | `apps/web/src/app/api/test-hosts/config.ts:38-45` (different literal example values: `c_test_1`/"Test Hotel" vs the panel's `c_8f3a`/"Hotel Example Group") | needs live | shape matches; the panel's literal IDs are illustrative, not a code requirement — no real per-person identity reaches the backend in production yet |
| em-token | "Today: Does not exist… pilot uses one shared invite token" | `apps/web/src/app/api/test-hosts/[name]/obi-token/route.ts:30-37` | drifted | the described JWT (iss/aud=obi/sub/iat/exp/company_id/company_name/integration, signed, `kid` in header) is built and tested; only real-platform wiring is outstanding |
| em-token | "Default: no values: general pages only" | `apps/web/src/app/api/test-hosts/config.ts:35` (`businessClaims: null` for `"none"`) | confirmed | structurally, for the test-host scaffolding |
| em-token | "Never in a URL, a cookie, web storage, a log line" | `apps/web/src/features/embed/iframe-bridge.ts:27`; `apps/web/src/features/embed/loader.ts:18-19` | confirmed | |
| em-button | "Accepts the note only from parent window, only from an allow-listed domain" | `apps/web/src/features/embed/iframe-bridge.ts:44-52`; tested `apps/web/src/features/embed/tests/iframe-bridge.test.ts:41-57,90-98` | confirmed | |
| em-button | "CSP frame-ancestors built at request time; empty outside local: 403" | `apps/web/src/middleware.ts:27-49`; `apps/web/src/features/embed/csp.ts:41-47` | confirmed | |
| em-button | Code location `app/embed/page.tsx — the frame's page (planned)` | `apps/web/src/app/embed/page.tsx:22-25` | drifted | not planned, already built |
| em-loader | "Today: Does not exist. The widget is embedded straight into a platform page and reads a shared pilot token from the URL." | `apps/web/src/features/embed/loader.ts:1-232`; `apps/web/src/features/embed/tests/loader.test.ts:1-216` | drifted | `obi.js` loader is fully built and unit-tested, bundled via `apps/web/package.json:9`'s `build:obi` script |
| em-loader | `Obi.init({tokenUrl})`; click-time fetch; postMessage to exact origin; silent renewal | `apps/web/src/features/embed/loader.ts:80-120,167-175,191-199` | confirmed | tested in `loader.test.ts:92-164` |
| em-loader | "Obi.clear() forgets note, empties chat, hides company name, blocks sending until a new note arrives" | `apps/web/src/features/embed/loader.ts:201-208`; `apps/web/src/app/embed/embed-frame.tsx:35`; `apps/web/src/features/chat/api/chat-client.ts:29-32` | drifted | `clear()`/`obi:clear` forgets the token and closes the panel, but there is no "blocks sending" gate — an absent token degrades to the general-only path rather than blocking |
| em-backend | Today: one shared CHAT_API_KEY; principal/knowledge_scope from body | `apps/web/src/features/chat/server/route-handlers.ts:112-119` (`toBackendChatBody` still sends `principal`/`knowledge_scope` from the body) | confirmed | note: the body-scope path and the new `X-Obi-Token` header are sent simultaneously today — dual-path, not yet a full cutover |
| d-curated | `CuratedKnowledgeEntry` table | n/a | missing | fully backend, owned by `platform/db/models.py:548-569` in `apps/automation` |

## Not on the design page

- `apps/web/src/app/test-hosts/multi/page.tsx` + `multi-user-content.tsx` — the multi-user switcher proving per-user identity live (git `59385f4`), not named by any panel in this assignment.
- `apps/web/src/app/api/test-hosts/config.ts` and its four `TEST_HOSTS` entries (RS256 key envs, issuer keys) — local-only scaffolding for `em-token`/`em-backend`, not itself named in the design panels.
- `apps/web/src/features/chat/ui/menu.tsx`, `menu-item.tsx`, `icon-button.tsx`, `language-menu.tsx`, `contour-background.tsx`, `assistant-mark.tsx`, `image-lightbox.tsx`, `typing-indicator.tsx` — UI primitives with their own test files, not individually named on any panel.
- `apps/web/src/components/ui/button.tsx` and `apps/web/src/components/README.md` — an unused/placeholder-adjacent `components/` root (no other file in `apps/web/src` imports `button.tsx`).
- `apps/web/src/platform/README.md` — a documentation stub for the `platform/` folder rule, not a panel claim.
- `apps/web/src/test-stubs/server-only.ts` — a test-only shim so Vitest can import server-only modules.
- `apps/web/src/app/(site)/dev-preview-backdrop.tsx` — dev-only decorative wrapper, explicitly "safe to delete; not part of the product" per its own docstring.
- `packages/contracts/src/token-claims.json` — a JSON Schema for the token claim set, already built (see `cm-contracts` verdict above).
