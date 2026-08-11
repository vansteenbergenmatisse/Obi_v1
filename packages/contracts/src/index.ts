/**
 * Cross-boundary contract types for Omniboost RAG.
 *
 * SOURCE OF TRUTH: `src/openapi/chat.yaml`. The interfaces below are
 * hand-written so `apps/web` and the Python automation API agree on shapes;
 * `apps/automation` defines its own Pydantic body models directly against the
 * same wire shapes (PLAN 4.4) rather than generating from this file, so there
 * is no `python/` sibling today.
 *
 * No logic and no database models live here — shapes only.
 */

// ---- Chat: request ----------------------------------------------------------

/**
 * An inline image attached to a chat turn (file-picker/clipboard-paste
 * attachment or a page screenshot capture). `data` is base64-encoded, no
 * data URI prefix. Per ADR-0009 decision 2, the web client only ever puts
 * `images` on the newest turn when resending `history` — the backend does
 * not enforce that shape structurally, it simply passes through whatever a
 * caller sends.
 */
export interface ImageAttachment {
  /** MIME type of the image, e.g. `image/png`. */
  mediaType: string;
  /** Base64-encoded image bytes. */
  data: string;
}

/**
 * One turn of conversation history. Distinct from `apps/web`'s feature-owned
 * render view-model (also named `ChatMessage` there) — this is the wire shape.
 */
export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  /**
   * Images attached to this turn (ADR-0009). Optional — most turns carry
   * none; when present, sent through a second, independent vision-analysis
   * call, never through citation enforcement (ADR-0009 decision 4).
   */
  images?: ImageAttachment[];
}

export interface ChatRequest {
  /**
   * Existing conversation to continue. Omit to start a new conversation; the
   * server mints and returns a `conversationId` on the first streamed event.
   */
  conversationId?: string;
  /**
   * Full turn history, oldest first, ending on a user turn. The server is
   * stateless per request — the caller resends the whole history every call.
   */
  history: ChatTurn[];
  /**
   * Caller-self-reported principal id used for page-level ACL scoping.
   * Trusted only as far as the deployment trusts the calling web proxy
   * (ADR-0004) — absent/unverified never widens access.
   */
  principal?: string;
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
  /** Direct URL to the source page (or anchor within it). May be empty if unavailable. */
  url: string;
  /** Confluence page version the evidence was drawn from. Not currently populated. */
  version?: number;
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
  /**
   * Links to the `query_trace` row for `PATCH /chat/{traceId}/feedback`.
   * Null only if the trace write itself failed — feedback is simply
   * unavailable for that turn, never a bypass of anything.
   */
  traceId: string | null;
  /**
   * True when the pipeline refused below `refusal_min_rerank_score`; the UI
   * should route to a human instead of treating `answer` as grounded.
   */
  refused: boolean;
  /**
   * Vision-analysis text for any images on the turn (ADR-0009 decision 5),
   * appended after the grounded answer and rendered as its own labeled
   * block — never itself carrying a citation marker. Optional: absent/null
   * when the turn had no image, or before the backend implements 7.3.
   */
  imageAnalysis?: string | null;
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

// ---- Chat: feedback ----------------------------------------------------------

/** `PATCH /chat/{traceId}/feedback` body: thumbs down (-1) or thumbs up (1). */
export interface FeedbackRequest {
  feedback: -1 | 1;
}

export interface FeedbackResponse {
  ok: boolean;
}

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
