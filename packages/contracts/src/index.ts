/**
 * Cross-boundary contract types for Omniboost RAG.
 *
 * SOURCE OF TRUTH: `src/openapi/chat.yaml`. The interfaces below are
 * hand-written for Phase 1 so `apps/web` and the Python automation API can
 * agree on shapes today. In a later phase they will be GENERATED from the
 * OpenAPI file (TypeScript here, Pydantic models under a `python/` sibling),
 * and this hand-written file will be replaced by the generated output.
 *
 * No logic and no database models live here — shapes only.
 */

// ---- Chat: request ----------------------------------------------------------

export interface ChatRequest {
  /**
   * Existing conversation to continue. Omit to start a new conversation; the
   * server mints and returns a `conversationId` on the first streamed event.
   */
  conversationId?: string;
  /** The user's message / question. */
  message: string;
}

// ---- Chat: streamed response ------------------------------------------------

/**
 * A single citation backing an answer, pointing at the Confluence source that
 * supports a span of the answer.
 */
export interface Citation {
  /** Stable id for this citation within the response. */
  id: string;
  /** Confluence page the evidence came from. */
  pageId: string;
  /** Human-readable page title at retrieval time. */
  title: string;
  /** Direct URL to the source page (or anchor within it). */
  url: string;
  /** Confluence page version the evidence was drawn from. */
  version: number;
  /** Optional quoted snippet of the supporting evidence. */
  snippet?: string;
}

/** Kinds of events streamed over the chat SSE channel. */
export type ChatStreamEventType = "start" | "token" | "citations" | "done" | "error";

/** Emitted once at the start of a stream to hand back the conversation id. */
export interface ChatStartEvent {
  type: "start";
  conversationId: string;
}

/** An incremental chunk of answer text. */
export interface ChatTokenEvent {
  type: "token";
  /** Answer text delta to append to the rendered answer. */
  delta: string;
}

/** The citations backing the answer, typically emitted before `done`. */
export interface ChatCitationsEvent {
  type: "citations";
  citations: Citation[];
}

/** Terminal success event. */
export interface ChatDoneEvent {
  type: "done";
  /** Full assembled answer text, for clients that did not accumulate tokens. */
  answer: string;
  citations: Citation[];
}

/** Terminal error event. */
export interface ChatErrorEvent {
  type: "error";
  error: string;
}

/** Discriminated union of everything that can arrive on the chat stream. */
export type ChatStreamEvent =
  | ChatStartEvent
  | ChatTokenEvent
  | ChatCitationsEvent
  | ChatDoneEvent
  | ChatErrorEvent;

// ---- Confluence webhook envelope -------------------------------------------

/** Lifecycle of a Confluence page as reported by a webhook delivery. */
export type ConfluenceEventType =
  | "page_created"
  | "page_updated"
  | "page_removed"
  | "page_restored";

/** Publication status of the page at the time of the event. */
export type ConfluencePageStatus = "current" | "draft" | "trashed" | "historical";

/**
 * Normalized envelope for an inbound Confluence webhook delivery. This is the
 * shape the automation API receives at `POST /confluence/events`.
 */
export interface ConfluenceEventEnvelope {
  /** What happened to the page. */
  eventType: ConfluenceEventType;
  /** Confluence page id the event concerns. */
  pageId: string;
  /** Page version number after the event. */
  version: number;
  /** Space the page belongs to. */
  spaceId: string;
  /** Page status after the event. */
  status: ConfluencePageStatus;
  /** ISO-8601 timestamp of the event. */
  timestamp: string;
  /** Unique delivery id, used for idempotent processing / dedup. */
  deliveryId: string;
}
