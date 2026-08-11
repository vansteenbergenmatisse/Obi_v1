/**
 * chat — public feature root.
 *
 * The ONE entrypoint for this feature. Routes and any other external code must
 * import from here (`@/features/chat`), never reach into `ui/`, `api/`, `model/`,
 * or `server/` directly. Internals stay free to move behind this surface.
 */
export { ChatWidget } from "./ui/chat-widget";
export { ChatSessionProvider } from "./ui/chat-session-provider";
export type { ChatMessage, MessageRole, MessageStatus } from "./model/messages";
export { handlePostChat, handlePatchFeedback } from "./server/route-handlers";
