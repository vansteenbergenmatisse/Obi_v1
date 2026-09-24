/**
 * chat — public feature root, the CLIENT-safe entrypoint.
 *
 * The entrypoint for this feature's browser-safe surface (UI, the client session hook, the
 * client chat API). Client and external code import from here (`@/features/chat`), never reach
 * into `ui/`, `api/`, or `model/` directly.
 *
 * Deliberately does NOT re-export `server/route-handlers.ts`. That module reaches
 * `@/platform/automation-api` → `import "server-only"` (it injects the `CHAT_API_KEY` host secret),
 * so a barrel that mixes it with browser-safe code breaks the client bundle the moment a
 * `"use client"` module imports this file (Next resolves the whole barrel's module graph before
 * tree-shaking can drop the unused half) — it 500-ed `/embed` via `app/embed/embed-frame.tsx`.
 * The server route entrypoints import `@/features/chat/server` instead — the same client/server
 * split `features/embed/index.ts` already documents for its `platforms.ts`.
 */
export { ChatWidget } from "./ui/chat-widget";
// FloatingFrame + PanelBody are the open-state panel, used directly by the `/embed` frame
// (app/embed/embed-frame.tsx) which owns its own open/close rather than mounting ChatWidget.
export { FloatingFrame } from "./ui/floating-frame";
export { PanelBody } from "./ui/panel-body";
export { ChatSessionProvider, useChatSession } from "./ui/chat-session-provider";
// The `/embed` frame subscribes this to clear stale UI when the backend rejects the token (401).
export { onUnauthorized } from "./api/chat-client";
export type { ChatMessage, MessageRole, MessageStatus } from "./model/messages";
