/**
 * Server-side input validation for the chat proxy (C3). Deliberately does not duplicate the
 * automation API's business-rule caps (`chat_max_history_turns`, `chat_max_message_chars`) —
 * that config is the backend's, and hardcoding a second copy here would drift from it. This
 * only rejects structurally invalid input and enforces a generous resource-exhaustion ceiling
 * before spending a network round trip; the backend remains the source of truth for its own
 * limits and returns 400 if they're exceeded, which the proxy forwards as-is.
 */
import type { ChatRequest, ChatTurn, FeedbackRequest } from "@omniboost/contracts";

export type ParseResult<T> = { ok: true; value: T } | { ok: false; error: string };

const MAX_HISTORY_TURNS = 200;
const MAX_TURN_CHARS = 20_000;

function isChatTurn(value: unknown): value is ChatTurn {
  if (typeof value !== "object" || value === null) return false;
  const turn = value as Record<string, unknown>;
  // No minimum content length — the backend has none either (only a max, `_validate_history` in
  // router.py). An image-only turn (ADR-0009 decision 4 / PLAN 7.5) sends content: "" while it's
  // the newest turn; once it ages out of "newest" its image is dropped too (decision 2: images are
  // only ever resent on the newest turn), leaving neither content nor images. Requiring non-empty
  // content here (even conditionally on images) breaks every later turn in that same conversation
  // (PLAN 7.8 bug E) — this is a structural shape check, not a business rule the proxy should own.
  return (
    (turn.role === "user" || turn.role === "assistant") &&
    typeof turn.content === "string" &&
    turn.content.length <= MAX_TURN_CHARS
  );
}

export function parseChatRequestBody(json: unknown): ParseResult<ChatRequest> {
  if (typeof json !== "object" || json === null) {
    return { ok: false, error: "request body must be a JSON object" };
  }
  const body = json as Record<string, unknown>;

  if (body.conversationId !== undefined && typeof body.conversationId !== "string") {
    return { ok: false, error: "conversationId must be a string" };
  }
  if (body.principal !== undefined && typeof body.principal !== "string") {
    return { ok: false, error: "principal must be a string" };
  }
  if (!Array.isArray(body.history) || body.history.length === 0) {
    return { ok: false, error: "history must be a non-empty array" };
  }
  if (body.history.length > MAX_HISTORY_TURNS) {
    return { ok: false, error: `history exceeds ${MAX_HISTORY_TURNS} turns` };
  }
  if (!body.history.every(isChatTurn)) {
    return {
      ok: false,
      error: "history turns must have role user|assistant and content within the length limit",
    };
  }
  const history = body.history as ChatTurn[];
  if (history[history.length - 1].role !== "user") {
    return { ok: false, error: "history must end on a user turn" };
  }

  return {
    ok: true,
    value: {
      conversationId: body.conversationId as string | undefined,
      history,
      principal: body.principal as string | undefined,
    },
  };
}

export function parseFeedbackBody(json: unknown): ParseResult<FeedbackRequest> {
  if (typeof json !== "object" || json === null) {
    return { ok: false, error: "request body must be a JSON object" };
  }
  const body = json as Record<string, unknown>;
  if (body.feedback !== -1 && body.feedback !== 1) {
    return { ok: false, error: "feedback must be -1 or 1" };
  }
  return { ok: true, value: { feedback: body.feedback } };
}
