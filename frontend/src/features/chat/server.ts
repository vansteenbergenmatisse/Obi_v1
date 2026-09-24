/**
 * chat — SERVER public root (PLAN 11.1c, ADR-0014).
 *
 * The server-only half of the chat feature's public surface: the App Router entrypoints
 * (`app/api/chat/route.ts`, `app/api/chat/[traceId]/feedback/route.ts`) import the proxy handlers
 * from here (`@/features/chat/server`), NOT from the client root (`@/features/chat`).
 *
 * These handlers inject the `CHAT_API_KEY` host secret server-side (via `@/platform/automation-api`),
 * so this module carries `import "server-only"`: a future accidental import from a `"use client"`
 * module fails loudly at build time instead of silently shipping the secret path into the browser
 * bundle. This is the same split `features/embed` uses for its `platforms.ts`.
 */
import "server-only";

export { handlePostChat, handlePatchFeedback } from "./server/route-handlers";
