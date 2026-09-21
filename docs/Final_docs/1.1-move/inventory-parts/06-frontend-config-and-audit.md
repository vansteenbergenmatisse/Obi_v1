# 06 · Frontend config reads + apps/web audit

Repo root: `/Users/matissevansteenbergen/Downloads/AGENTIC WORKLFOWS/OMNIBOOST/RAG-TOAST-omniboost-version2`
Frontend app: `apps/web` (Next.js). Path alias `@/*` → `./src/*` (tsconfig.json:17-18) — internal only, never leaves the app.

## (A) Where the widget reaches the repo-root `config/knowledge_scopes.json`

The scope list is NOT imported into the client bundle. Next forbids importing a JSON from outside the app root, so the widget keeps a **hand-mirrored copy** and a build-time drift guard reads the canonical file:

| # | Path : line | What it does |
|---|---|---|
| 1 | `apps/web/src/features/chat/model/knowledge-scopes.ts:14-19` | The mirror. Hardcoded `KNOWLEDGE_SCOPES` array (obi-general-test / obi-mews-test / obi-operacloud-test / obi-toast-test). Does NOT read the JSON. Header comment (lines 5-11) names `config/knowledge_scopes.json` as canonical. |
| 2 | `apps/web/src/features/chat/tests/knowledge-scopes.test.ts:18` | **The one runtime read.** `resolve(here, "../../../../../../config/knowledge_scopes.json")` — six dirs up from `apps/web/src/features/chat/tests` to the repo root `config/`. `readFileSync` (line 26), asserts the mirror equals the canonical `scopes[].name` list in order. |

So exactly **one place reads `knowledge_scopes.json`** (the drift-guard test), expecting repo-root `config/knowledge_scopes.json` via a six-level `../` climb.

**Breaks on the move to `knowledge-base/config/knowledge_scopes.json`:** the hardcoded relative path at `knowledge-scopes.test.ts:18` must be repointed. All other `knowledge_scopes` hits (route-handlers, validation, provider, ~30 test/comment refs) use the string field `knowledgeScope`/`knowledge_scope` on the wire, not the file — unaffected by a file move.

### Bonus: a second repo-root config read (same pattern, same risk)
- `apps/web/src/features/embed/platforms.ts:29` — `resolve(here, "../../../../../config/platforms.json")` (five up), runtime default for the active-domains list, overridable via `PLATFORMS_PATH`. If `platforms.json` also moves under `knowledge-base/config/`, this default path breaks too.

## (B) apps/web/src map — what does what

Top level: `app/`, `components/`, `features/`, `platform/`, `test-stubs/`, plus `middleware.ts`, `test-setup.ts`. No `shared/` dir exists.

- **app/** — Next routes/composition. `(site)`, `embed/` (embed frame + layout, scope from verified token), `test-hosts/` (mews|toast|opera-cloud|multi|none stub host pages), `api/chat` (proxy to automation), `api/internal/active-domains`, `api/test-hosts` (+ `jwks/[issuer]` local JWKS via next.config rewrite).
- **components/** — reusable UI. Only `ui/button.tsx` today.
- **features/chat/** — the widget: `ui/` (provider/state machine, launcher, teaser, panel, message list/bubble, composer, menus, scope-menu, i18n-driven copy), `api/` (SSE `chat-client`), `model/` (messages, i18n, `knowledge-scopes` mirror), `server/` (`route-handlers` proxy + `validation`), `tests/`. Public root `index.ts`.
- **features/embed/** — embed plumbing: `csp.ts`, `iframe-bridge.ts`, `loader.ts`, `platforms.ts` (active-domain list from `config/platforms.json`). Public root `index.ts`.
- **platform/automation-api/** — generic authenticated (`CHAT_API_KEY`) HTTP client to the Python `apps/automation` service. `client.ts` + `index.ts`; consumed by `features/chat/server`.
- **test-stubs/** — `server-only.ts` stub for tests.

### Cross-folder references that could break on a frontend folder rename
- **File-path climbs leaving apps/web (WILL break):** `chat/tests/knowledge-scopes.test.ts:18` (`../×6 → config/knowledge_scopes.json`) and `embed/platforms.ts:29` (`../×5 → config/platforms.json`). Both hardcode the number of `../` levels and the repo-root `config/` location — sensitive to BOTH the config move and any apps/web depth change.
- **`apps/automation` references (won't break on rename):** all in `platform/automation-api/*`, `features/chat/server/route-handlers.ts`, and doc/comment strings — these are runtime HTTP `baseUrl` calls (`http://backend.internal`), not source imports. Renaming folders does not touch them; only a changed backend base URL would.
- **Path alias `@/*`:** resolves to `./src/*` only — no alias reaches outside apps/web.
