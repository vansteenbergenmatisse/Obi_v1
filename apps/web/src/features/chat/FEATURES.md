This file documents every feature in apps/web/src/features. Each block below maps to one folder in that directory. A feature without a block here is undocumented and incomplete.

## chat

- **What it does:** Renders the user-facing chat interface and proxies chat requests to the Python automation API, streaming answers and citations back to the browser.
- **Path / owning app:** `apps/web/src/features/chat` — owned by `apps/web`.
- **Language / framework / runtime:** TypeScript, Next.js 15 (App Router) + React 19, Node.js LTS (server) and the browser (client components).
- **Deployment unit:** Ships inside the `web` Next.js application deployment.
- **Exported symbols (`index.ts`):** None yet. The public surface lands with the Phase 4 chat UI.
- **Allowed importers:** `apps/web/src/app` (routes/pages) only. No other feature or application imports it.
- **Contracts consumed:** `@omniboost/contracts` — `ChatRequest`, `ChatStreamEvent` (and members: `ChatStartEvent`, `ChatTokenEvent`, `ChatCitationsEvent`, `ChatDoneEvent`, `ChatErrorEvent`), `Citation`.
- **External systems called:** The Python automation API (`apps/automation`, `POST /chat`, SSE) — reached via the `apps/web/src/app/api/chat` route handler (currently a 501 stub).
- **Database tables owned:** None. Conversation persistence is owned by `apps/automation`.
- **Where it validates untrusted input:** The `api/chat` route handler will validate the inbound `ChatRequest` against the contract before proxying. Not yet implemented (Phase 4).
- **Shared components used:** None yet. Design values come from `@omniboost/design-tokens` via Tailwind utilities.
- **Tests location / risky paths:** `apps/web/src/features/chat/tests` (none yet). Risky paths to cover in Phase 4: SSE stream parsing, partial/aborted streams, and citation rendering.
- **Run / test commands:** Run: `pnpm --filter web dev`. Build: `pnpm --filter web build`. Test: None yet (test runner is wired in Phase 4).
