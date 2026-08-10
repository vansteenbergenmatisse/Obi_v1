/**
 * Chat feature — view-model types.
 *
 * These describe how a message is *rendered*, which is feature-owned domain and
 * intentionally separate from the wire contract in `@omniboost/contracts`
 * (`ChatRequest` / `ChatStreamEvent`). The client maps wire events onto these.
 */
import type { Citation } from "@omniboost/contracts";

export type MessageRole = "user" | "assistant";

/**
 * Lifecycle of an assistant turn as the UI renders it. `refused` means the pipeline
 * declined to answer (below the rerank-score refusal threshold) and the turn should
 * be routed to a human rather than presented as a grounded answer.
 */
export type MessageStatus = "streaming" | "complete" | "refused" | "error";

/** A single rendered turn in the conversation. */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  text: string;
  /** Present on assistant turns once citations arrive. */
  citations?: Citation[];
  /** Only meaningful for assistant turns; user turns are always complete. */
  status: MessageStatus;
  /** Set from the stream's `done` event; enables the feedback control once present. */
  traceId?: string;
  /** The rating the user has already submitted for this turn, if any. */
  feedback?: -1 | 1;
}
