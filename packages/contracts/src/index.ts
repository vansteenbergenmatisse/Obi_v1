/**
 * Cross-boundary contract types for Omniboost RAG.
 *
 * SOURCE OF TRUTH: `src/openapi/chat.yaml`. The interfaces below are
 * hand-written so `frontend` and the Python automation API agree on shapes;
 * `backend` defines its own Pydantic body models directly against the
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
 * One turn of conversation history. Distinct from `frontend`'s feature-owned
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
  /**
   * Which third-party platform's documentation this deployment/embed is
   * scoped to (ADR-0011 decision 6), e.g. `"mews"`, `"opera-cloud"`,
   * `"toast"`. Resolved once per request, not inferred from message
   * content. Omitted or unrecognized falls back to the deployment default
   * (or `general` alone) server-side — never a hard error.
   */
  knowledgeScope?: string;
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

/**
 * Closed refusal-reason taxonomy (ADR-0008 decision 4; `off_topic` added 2026-09-12).
 * `off_topic` is a friendly "ask me about the docs" redirect with no human hand-off;
 * the other three route to a human. Mirrors the backend `RefusalReason` literal.
 */
export type RefusalReason =
  | "no_candidates"
  | "off_topic"
  | "weak_score"
  | "no_citations";

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
   * should not treat `answer` as grounded. Whether to route to a human depends
   * on `refusalReason` (see below) — `off_topic` is a redirect, not a hand-off.
   */
  refused: boolean;
  /**
   * The refusal category (ADR-0008 decision 4; `off_topic` added 2026-09-12),
   * present only when `refused` is true. The UI shows the human-hand-off CTA for
   * `no_candidates | weak_score | no_citations` and a softer redirect (no CTA)
   * for `off_topic`. Absent/null on a non-refused turn, and on older backends
   * that did not yet send it — treat a missing value as "show the hand-off CTA."
   */
  refusalReason?: RefusalReason | null;
  /**
   * Vision-analysis text for any images on the turn (ADR-0009 decision 5),
   * appended after the grounded answer and rendered as its own labeled
   * block — never itself carrying a citation marker. Optional: absent/null
   * when the turn had no image, or before the backend implements 7.3.
   */
  imageAnalysis?: string | null;
  /**
   * True when the query was judged too vague to search well (PLAN 9.3,
   * ADR-0008 decision 3) and the pipeline bypassed rewrite/retrieval/
   * refusal to ask a clarifying question instead. A still-open
   * conversation turn, not a refusal — `refused` stays false on this path.
   */
  needsClarification?: boolean;
  /**
   * The clarifying question, identical to `answer` on this path — present
   * as its own field so a client can distinguish a clarification turn
   * without string-matching `answer`.
   */
  clarificationQuestion?: string | null;
  /**
   * 2-4 concrete options the clarifying question offers, for a client to
   * render as quick-reply chips (PLAN 9.5). Absent/null when the turn is
   * not a clarification turn.
   */
  clarificationOptions?: string[] | null;
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

// ---- Obi embed: iframe postMessage contract (PLAN 11.1c, ADR-0014) ---------

export type {
  ObiMessage,
  ObiMessageType,
  ObiOpenMessage,
  ObiTokenMessage,
  ObiClearMessage,
} from "./iframe-messages";
export { OBI_MESSAGE_TYPES } from "./iframe-messages";
