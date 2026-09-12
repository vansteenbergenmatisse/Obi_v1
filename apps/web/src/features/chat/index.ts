/**
 * chat — public feature root.
 *
 * The ONE entrypoint for this feature. Routes and any other external code must
 * import from here (`@/features/chat`), never reach into `ui/`, `api/`, `model/`,
 * or `server/` directly. Internals stay free to move behind this surface.
 */
export { ChatWidget } from "./ui/chat-widget";
// FloatingFrame + PanelBody are the open-state panel, used directly by the `/embed` frame
// (app/embed/embed-frame.tsx) which owns its own open/close rather than mounting ChatWidget.
export { FloatingFrame } from "./ui/floating-frame";
export { PanelBody } from "./ui/panel-body";
export { ChatSessionProvider } from "./ui/chat-session-provider";
export type { ChatMessage, MessageRole, MessageStatus } from "./model/messages";
export { handlePostChat, handlePatchFeedback } from "./server/route-handlers";
