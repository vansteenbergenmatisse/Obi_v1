/**
 * Chat route handler — a thin entrypoint.
 *
 * It only composes the `chat` feature's exported server handler; the proxy behavior
 * (validation, auth, streaming passthrough to `backend`) is owned end to end by
 * `features/chat/server` and reached through the feature's public root.
 */
import { handlePostChat } from "@/features/chat";

export const POST = handlePostChat;
