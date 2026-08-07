/**
 * Chat feature — view-model types.
 *
 * These describe how a message is *rendered*, which is feature-owned domain and
 * intentionally separate from the wire contract in `@omniboost/contracts`
 * (`ChatRequest` / `ChatStreamEvent`). The client maps wire events onto these.
 */
import type { Citation } from "@omniboost/contracts";

export type MessageRole = "user" | "assistant";

/** Lifecycle of an assistant turn as the UI renders it. */
export type MessageStatus = "streaming" | "complete" | "error";

/** A single rendered turn in the conversation. */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  text: string;
  /** Present on assistant turns once citations arrive. */
  citations?: Citation[];
  /** Only meaningful for assistant turns; user turns are always complete. */
  status: MessageStatus;
}
