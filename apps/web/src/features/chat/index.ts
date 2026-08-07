/**
 * chat — public feature root.
 *
 * The ONE entrypoint for this feature. Routes and any other external code must
 * import from here (`@/features/chat`), never reach into `ui/`, `api/`, or
 * `model/` directly. Internals stay free to move behind this surface.
 */
export { ChatPanel } from "./ui/chat-panel";
export type { ChatMessage, MessageRole, MessageStatus } from "./model/messages";
