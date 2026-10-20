/**
 * Visibility-probe route entrypoint (sync-rules Task 5, ADR-widget-hides-via-visibility-probe) — a thin entrypoint, like
 * `app/api/chat/route.ts`.
 *
 * It only composes the `chat` feature's exported server handler; the proxy behavior (user-token
 * threading, host-key injection, verbatim passthrough of `/chat/visibility`) is owned end to end by
 * `features/chat/server` and reached through the feature's SERVER public root (never the client
 * root), so the host secret never enters a client bundle.
 */
import { handleGetVisibility } from "@/features/chat/server";

export const GET = handleGetVisibility;
