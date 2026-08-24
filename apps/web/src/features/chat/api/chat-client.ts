/**
 * Chat feature — browser-side client.
 *
 * Speaks the wire contract from `@omniboost/contracts` against this app's own `/api/chat`
 * route (which proxies to the Python automation API). SSE parsing lives here so the UI only
 * ever sees typed events, never raw stream bytes.
 */
import type {
  ChatCitationsEvent,
  ChatDoneEvent,
  ChatRequest,
  ChatStreamEvent,
  FeedbackRequest,
  FeedbackResponse,
} from "@omniboost/contracts";
import { getWidgetAccessToken } from "./access-token";

const CHAT_ENDPOINT = "/api/chat";
const ACCESS_TOKEN_HEADER = "x-widget-access-token";

/** Attaches the widget's shared invite token (idea #6) when one has been captured; omitted
 * entirely when absent so the server sees a plain missing header, not an empty one. */
function accessTokenHeaders(): Record<string, string> {
  const token = getWidgetAccessToken();
  return token ? { [ACCESS_TOKEN_HEADER]: token } : {};
}

/** Thrown when the fetch itself fails, or the server rejects the request before any
 * streaming starts (auth/validation/rate-limit/config failures — never a mid-stream event). */
export class ChatRequestError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ChatRequestError";
    this.status = status;
  }
}

export interface ChatStreamHandlers {
  onStart?: (conversationId: string) => void;
  onToken?: (delta: string) => void;
  onCitations?: (citations: ChatCitationsEvent["citations"]) => void;
  onDone?: (event: ChatDoneEvent) => void;
  onError?: (message: string) => void;
}

/** Streams one chat turn. Resolves once the stream ends (successfully or via a mid-stream
 * `error` event, which is reported through `handlers.onError`, not a thrown error). */
export async function streamChat(
  request: ChatRequest,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(CHAT_ENDPOINT, {
      method: "POST",
      headers: { "content-type": "application/json", ...accessTokenHeaders() },
      body: JSON.stringify(request),
      signal,
    });
  } catch (cause) {
    throw new ChatRequestError(cause instanceof Error ? cause.message : "network error", 0);
  }

  if (!response.ok || !response.body) {
    const body = (await response.json().catch(() => null)) as { error?: string } | null;
    throw new ChatRequestError(body?.error ?? `request failed (${response.status})`, response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let separatorIndex = buffer.indexOf("\n\n");
      while (separatorIndex !== -1) {
        dispatchSseEvent(buffer.slice(0, separatorIndex), handlers);
        buffer = buffer.slice(separatorIndex + 2);
        separatorIndex = buffer.indexOf("\n\n");
      }
    }
  } finally {
    reader.releaseLock();
  }
}

function dispatchSseEvent(rawEvent: string, handlers: ChatStreamHandlers): void {
  const dataLine = rawEvent.split("\n").find((line) => line.startsWith("data:"));
  if (!dataLine) return;

  let event: ChatStreamEvent;
  try {
    event = JSON.parse(dataLine.slice("data:".length).trim()) as ChatStreamEvent;
  } catch {
    handlers.onError?.("received a malformed event from the server");
    return;
  }

  switch (event.type) {
    case "start":
      handlers.onStart?.(event.conversationId);
      return;
    case "token":
      handlers.onToken?.(event.delta);
      return;
    case "citations":
      handlers.onCitations?.(event.citations);
      return;
    case "done":
      handlers.onDone?.(event);
      return;
    case "error":
      handlers.onError?.(event.error);
      return;
  }
}

export async function sendFeedback(
  traceId: string,
  feedback: FeedbackRequest["feedback"],
): Promise<FeedbackResponse> {
  const response = await fetch(`${CHAT_ENDPOINT}/${encodeURIComponent(traceId)}/feedback`, {
    method: "PATCH",
    headers: { "content-type": "application/json", ...accessTokenHeaders() },
    body: JSON.stringify({ feedback } satisfies FeedbackRequest),
  });
  const body = (await response.json().catch(() => null)) as (FeedbackResponse & { error?: string }) | null;
  if (!response.ok || !body) {
    throw new ChatRequestError(
      body?.error ?? `feedback failed (${response.status})`,
      response.status,
    );
  }
  return body;
}
