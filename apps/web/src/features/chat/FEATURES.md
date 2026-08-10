This file documents every feature in apps/web/src/features. Each block below maps to one folder in that directory. A feature without a block here is undocumented and incomplete.

## chat

- **What it does:** Renders the user-facing chat interface and proxies chat requests to the Python automation API, streaming answers and citations back to the browser; also proxies thumbs up/down feedback.
- **Path / owning app:** `apps/web/src/features/chat` — owned by `apps/web`.
- **Language / framework / runtime:** TypeScript, Next.js 15 (App Router) + React 19, Node.js LTS (server) and the browser (client components).
- **Deployment unit:** Ships inside the `web` Next.js application deployment.
- **Exported symbols (`index.ts`):** `ChatPanel` (the feature's root React component, rendered by the chat route); the view-model types `ChatMessage`, `MessageRole`, `MessageStatus`; and the server route handlers `handlePostChat`, `handlePatchFeedback` (composed by `app/api/chat/**/route.ts`). Internals (`ui/`, `api/`, `model/`, `server/`) are private behind this root.
- **Internal structure:** `ui/` (`chat-panel`, `message-list`, `composer` — feature-only components), `api/` (`chat-client` — browser SSE client over `/api/chat`), `model/` (`messages` — render view-model), `server/` (`route-handlers` — the Next.js proxy to `apps/automation`; `validation` — inbound shape checks, C3).
- **Allowed importers:** `apps/web/src/app` (routes/pages) only, and only via the public root `@/features/chat`. No other feature or application imports it.
- **Contracts consumed:** `@omniboost/contracts` — `ChatRequest`, `ChatTurn`, `ChatStreamEvent` (and members: `ChatStartEvent`, `ChatTokenEvent`, `ChatCitationsEvent`, `ChatDoneEvent`, `ChatErrorEvent`), `Citation`, `FeedbackRequest`, `FeedbackResponse`.
- **External systems called:** The Python automation API (`apps/automation`, `POST /chat` SSE + `PATCH /chat/{traceId}/feedback`) — reached via `server/route-handlers.ts` through `platform/automation-api`, composed by the `app/api/chat/**` route handlers.
- **Database tables owned:** None. Conversation and trace persistence is owned by `apps/automation`.
- **Where it validates untrusted input:** `server/validation.ts` — rejects malformed shape/JSON and enforces a resource-exhaustion body-size ceiling before any network call; the automation API's own business-rule caps (history length, per-turn length) remain authoritative and are forwarded verbatim on rejection.
- **Shared components used:** `@/components/ui/button` (`Button`, in the composer); the chat route wraps the panel in `@/components/layout/page-shell` (`PageShell`). Design values come from `@omniboost/design-tokens` via Tailwind utilities.
- **Tests location / risky paths:** `apps/web/src/features/chat/tests` — SSE stream parsing (multi-chunk, partial buffer boundaries), request validation edge cases, and the proxy's auth-header injection + error/streaming passthrough.
- **Run / test commands:** Run: `pnpm --filter web dev`. Build: `pnpm --filter web build`. Test: `pnpm --filter web test` (vitest).
