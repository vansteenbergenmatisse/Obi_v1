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

/** A rendered image on a user turn — the composer's local blob preview, kept alive for the life
 * of the conversation rather than revoked on send (PLAN 7.5), so the sent image stays visible and
 * clickable (`ImageLightbox`) in the thread. */
export interface MessageImage {
  id: string;
  previewUrl: string;
  alt: string;
}

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
  /** Images attached to this (user) turn, for local preview/zoom (PLAN 7.5). */
  images?: MessageImage[];
  /** Vision-analysis text for this (assistant) turn's images, from the `done` event's
   * `imageAnalysis` (ADR-0009 decision 5) — rendered as its own labeled block, never merged into
   * `text`, since it never passes through citation enforcement. */
  imageAnalysis?: string;
}

/** An image staged in the composer, ready to send: `mediaType`/`data` are the wire shape
 * (`ImageAttachment`); `previewUrl`/`alt` carry over into the sent message's local render. */
export interface SentImage {
  mediaType: string;
  data: string;
  previewUrl: string;
  alt: string;
}
