// @vitest-environment jsdom
/**
 * EmbedFrame — integration test for the embed logout lifecycle (slice S1, gaps LC-1/LC-4/LC-6).
 *
 * Renders the REAL frame: the real `ChatSessionProvider`, the real `PanelBody` composer, the real
 * `initIframeBridge`, and the real `chat-client` (with `fetch` stubbed). `window.parent` is
 * `window` in jsdom, so a `MessageEvent` dispatched with `source: window.parent` and an allowed
 * `origin` is exactly what the host loader's `postMessage` looks like to the bridge.
 *
 * The behavior under test is the wiring the frame adds: `obi:clear` must reach the session's
 * `restart()` (abort in-flight stream + clear thread + reset conversationId), not merely hide the
 * panel; and a backend 401 must drive the subscribed `onUnauthorized` handler to clear stale UI.
 * `restart()`'s own mechanics are already locked in by `chat-session-provider.test.tsx`.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ChatStreamEvent } from "@omniboost/contracts";
import { EmbedFrame } from "./embed-frame";

const ORIGIN = "https://app.mews.com";

function sse(event: ChatStreamEvent): string {
  return `data: ${JSON.stringify(event)}\n\n`;
}

function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(encoder.encode(chunks[index]));
        index += 1;
      } else {
        controller.close();
      }
    },
  });
}

function okStreamResponse(chunks: string[]): Response {
  return new Response(streamFromChunks(chunks), {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });
}

function postFromHost(data: unknown, origin: string = ORIGIN) {
  act(() => {
    window.dispatchEvent(
      new MessageEvent("message", { data, origin, source: window.parent }),
    );
  });
}

async function sendMessage(text: string) {
  const box = screen.getByRole("textbox", { name: /message/i });
  await userEvent.type(box, text);
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
}

/** A syntactically-valid JWT carrying display-only business claims (no real signature — the bridge
 * decodes claims for scope-equality only, never for auth). Mirrors iframe-bridge.test.ts. */
function jwtWithClaims(claims: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const payload = btoa(JSON.stringify(claims));
  return `${header}.${payload}.signature`;
}

describe("EmbedFrame lifecycle", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("LC-1/LC-4: obi:clear wipes the thread — a re-open shows an empty, fresh conversation", async () => {
    const requestBodies: Array<{ conversationId?: string }> = [];
    fetchMock.mockImplementation((_url: string, init?: RequestInit) => {
      requestBodies.push(init?.body ? JSON.parse(init.body as string) : {});
      return Promise.resolve(
        okStreamResponse([
          sse({ type: "start", conversationId: "conv-1" }),
          sse({ type: "done", answer: "First answer", citations: [], traceId: "trace-1", refused: false }),
        ]),
      );
    });

    render(<EmbedFrame allowedOrigins={[ORIGIN]} />);

    postFromHost({ type: "obi:open" });
    await screen.findByRole("textbox", { name: /message/i });

    await sendMessage("first question");
    expect(await screen.findByText("first question")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("First answer")).toBeInTheDocument());

    // Logout: the panel closes AND the conversation is torn down.
    postFromHost({ type: "obi:clear" });
    expect(screen.queryByRole("textbox", { name: /message/i })).not.toBeInTheDocument();

    // Re-open: the prior thread must be gone, not merely hidden.
    postFromHost({ type: "obi:open" });
    await screen.findByRole("textbox", { name: /message/i });
    expect(screen.queryByText("first question")).not.toBeInTheDocument();
    expect(screen.queryByText("First answer")).not.toBeInTheDocument();

    // ...and conversationId was reset: the next turn opens a brand-new conversation.
    await sendMessage("second question");
    await waitFor(() => expect(requestBodies).toHaveLength(2));
    expect(requestBodies[1].conversationId).toBeUndefined();
  });

  it("LC-4: obi:clear aborts an in-flight stream and a late event never lands in the thread", async () => {
    let capturedSignal: AbortSignal | undefined;
    let streamController: ReadableStreamDefaultController<Uint8Array> | undefined;
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        streamController = controller;
        controller.enqueue(encoder.encode(sse({ type: "start", conversationId: "conv-1" })));
      },
    });
    fetchMock.mockImplementation((_url: string, init?: RequestInit) => {
      capturedSignal = init?.signal ?? undefined;
      return Promise.resolve(
        new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }),
      );
    });

    render(<EmbedFrame allowedOrigins={[ORIGIN]} />);
    postFromHost({ type: "obi:open" });
    await screen.findByRole("textbox", { name: /message/i });

    await sendMessage("hanging question");
    await waitFor(() => expect(capturedSignal).toBeDefined());

    // Logout while the answer is still streaming.
    postFromHost({ type: "obi:clear" });
    expect(capturedSignal?.aborted).toBe(true);

    // The stream emits its answer AFTER logout — it must be dropped, not appended.
    act(() => {
      streamController?.enqueue(
        encoder.encode(
          sse({ type: "done", answer: "LATE ANSWER", citations: [], traceId: "trace-1", refused: false }),
        ),
      );
      streamController?.close();
    });

    postFromHost({ type: "obi:open" });
    await screen.findByRole("textbox", { name: /message/i });
    expect(screen.queryByText("LATE ANSWER")).not.toBeInTheDocument();
    expect(screen.queryByText("hanging question")).not.toBeInTheDocument();
  });

  it("LC-F1: a scope-changing obi:token renewal resets the active conversation (onScopeChange → restart)", async () => {
    const requestBodies: Array<{ conversationId?: string }> = [];
    fetchMock.mockImplementation((_url: string, init?: RequestInit) => {
      requestBodies.push(init?.body ? JSON.parse(init.body as string) : {});
      return Promise.resolve(
        okStreamResponse([
          sse({ type: "start", conversationId: "conv-1" }),
          sse({ type: "done", answer: "Mews answer", citations: [], traceId: "trace-1", refused: false }),
        ]),
      );
    });

    render(<EmbedFrame allowedOrigins={[ORIGIN]} />);
    postFromHost({ type: "obi:open" });
    await screen.findByRole("textbox", { name: /message/i });

    // Establish the first scope, then hold a real conversation under it.
    postFromHost({
      type: "obi:token",
      token: jwtWithClaims({ integration: "mews", company_id: "c1" }),
    });
    await sendMessage("mews question");
    expect(await screen.findByText("mews question")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Mews answer")).toBeInTheDocument());

    // A silent renewal into a DIFFERENT company/integration must tear the conversation down so no
    // prior-scope answer bleeds across — onScopeChange → restart() (LC-2/LC-3/LC-6).
    postFromHost({
      type: "obi:token",
      token: jwtWithClaims({ integration: "toast", company_id: "c2" }),
    });

    // A scope change is not a logout: the panel stays open, but the prior thread is gone.
    await waitFor(() =>
      expect(screen.queryByText("mews question")).not.toBeInTheDocument(),
    );
    expect(screen.queryByText("Mews answer")).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /message/i })).toBeInTheDocument();

    // ...and conversationId was reset: the next turn opens a brand-new conversation.
    await sendMessage("toast question");
    await waitFor(() => expect(requestBodies).toHaveLength(2));
    expect(requestBodies[1].conversationId).toBeUndefined();
  });

  it("LC-6: a backend 401 drives the subscribed onUnauthorized handler, clearing stale UI", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ error: "invalid token" }), { status: 401 }),
    );

    render(<EmbedFrame allowedOrigins={[ORIGIN]} />);
    postFromHost({ type: "obi:open" });
    await screen.findByRole("textbox", { name: /message/i });

    await sendMessage("question under a stale token");

    // The 401 fires onUnauthorized → restart() clears the thread (the stale user turn is gone).
    await waitFor(() =>
      expect(screen.queryByText("question under a stale token")).not.toBeInTheDocument(),
    );
  });
});
