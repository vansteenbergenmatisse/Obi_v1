/**
 * Chat feature — browser-side client.
 *
 * Thin wrapper over the app's own `/api/chat` route handler (which proxies to
 * the Python automation API). It speaks the wire contract from
 * `@omniboost/contracts` and surfaces a typed result the UI can render.
 *
 * The route handler is a 501 stub until Phase 4; `sendChat` handles that
 * honestly by returning a typed error rather than throwing, so the scaffold is
 * exercisable end to end today.
 */
import type { ChatRequest } from "@omniboost/contracts";

/** What the browser client hands back to the UI for one exchange. */
export type SendChatResult =
  | { ok: true; answer: string }
  | { ok: false; error: string; status: number };

const CHAT_ENDPOINT = "/api/chat";

export async function sendChat(
  request: ChatRequest,
  signal?: AbortSignal,
): Promise<SendChatResult> {
  let response: Response;
  try {
    response = await fetch(CHAT_ENDPOINT, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
      signal,
    });
  } catch (cause) {
    return {
      ok: false,
      status: 0,
      error: cause instanceof Error ? cause.message : "network error",
    };
  }

  if (!response.ok) {
    // The Phase-1 stub returns `{ error }` with 501; forward that shape.
    const body = (await response.json().catch(() => null)) as {
      error?: string;
    } | null;
    return {
      ok: false,
      status: response.status,
      error: body?.error ?? `request failed (${response.status})`,
    };
  }

  // Phase 4 replaces this with SSE parsing (start/token/citations/done). For
  // now the stub never reaches here; keep the happy path typed and minimal.
  const body = (await response.json().catch(() => ({}))) as { answer?: string };
  return { ok: true, answer: body.answer ?? "" };
}
