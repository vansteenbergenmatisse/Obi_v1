import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatStreamEvent } from "@omniboost/contracts";

const { getTokenMock } = vi.hoisted(() => ({
  getTokenMock: vi.fn(),
}));

vi.mock("@/features/embed", () => ({
  getToken: getTokenMock,
}));

import { onUnauthorized, sendFeedback, streamChat } from "../api/chat-client";

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

describe("streamChat", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    getTokenMock.mockReset();
    getTokenMock.mockReturnValue(null);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // panel r1-proxy · substep p0-s0_5-reg-retrieval-stage-1
  // The browser must call POST /api/chat on the widget's own origin, not the backend directly.
  it("r1_proxy_calls_the_widgets_own_origin_api_chat_route", async () => {
    fetchMock.mockResolvedValue(okStreamResponse([sse({ type: "start", conversationId: "c" })]));

    await streamChat({ history: [{ role: "user", content: "hi" }] }, {});

    const [url] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/chat");
  });

  // panel ov-widget · substep p0-s0_5-reg-system-overview
  // System-overview step 2: "The user asks. The widget calls its own proxy route." The browser
  // must POST to the widget's OWN same-origin proxy route, never straight at the automation
  // backend — the request target is a relative path, so it can carry no absolute backend host.
  it("ov_widget_user_asks_calls_its_own_proxy_route_not_the_backend_directly", async () => {
    fetchMock.mockResolvedValue(okStreamResponse([sse({ type: "start", conversationId: "c" })]));

    await streamChat({ history: [{ role: "user", content: "how do I refund a folio?" }] }, {});

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/chat");
    // A relative path (no scheme/host) proves the call stays on the widget's own origin and is not
    // pointed at the Python automation backend directly.
    expect(String(url)).not.toMatch(/^https?:\/\//);
    expect((init as RequestInit).method).toBe("POST");
  });

  it("attaches the Authorization bearer header when a token is present", async () => {
    getTokenMock.mockReturnValue("jwt-abc123");
    fetchMock.mockResolvedValue(okStreamResponse([sse({ type: "start", conversationId: "c" })]));

    await streamChat({ history: [{ role: "user", content: "hi" }] }, {});

    const [, init] = fetchMock.mock.calls[0];
    expect((init.headers as Record<string, string>).authorization).toBe("Bearer jwt-abc123");
  });

  it("omits the Authorization header when no token is present", async () => {
    getTokenMock.mockReturnValue(null);
    fetchMock.mockResolvedValue(okStreamResponse([sse({ type: "start", conversationId: "c" })]));

    await streamChat({ history: [{ role: "user", content: "hi" }] }, {});

    const [, init] = fetchMock.mock.calls[0];
    expect((init.headers as Record<string, string>).authorization).toBeUndefined();
  });

  it("dispatches start/token/citations/done in order from a single chunk", async () => {
    const events: ChatStreamEvent[] = [
      { type: "start", conversationId: "conv-1" },
      { type: "token", delta: "Hel" },
      { type: "token", delta: "lo" },
      {
        type: "citations",
        citations: [{ id: "1", pageId: "p1", title: "Page One", url: "https://x" }],
      },
      {
        type: "done",
        answer: "Hello",
        citations: [{ id: "1", pageId: "p1", title: "Page One", url: "https://x" }],
        traceId: "trace-1",
        refused: false,
      },
    ];
    fetchMock.mockResolvedValue(okStreamResponse([events.map(sse).join("")]));

    const seen: string[] = [];
    await streamChat({ history: [{ role: "user", content: "hi" }] }, {
      onStart: (id) => seen.push(`start:${id}`),
      onToken: (delta) => seen.push(`token:${delta}`),
      onCitations: (citations) => seen.push(`citations:${citations.length}`),
      onDone: (event) => seen.push(`done:${event.traceId}:${event.refused}`),
      onError: (message) => seen.push(`error:${message}`),
    });

    expect(seen).toEqual([
      "start:conv-1",
      "token:Hel",
      "token:lo",
      "citations:1",
      "done:trace-1:false",
    ]);
  });

  it("reassembles an event whose \\n\\n separator is split across chunks", async () => {
    const raw = sse({ type: "start", conversationId: "conv-2" });
    const splitPoint = raw.indexOf("\n\n") + 1; // split inside the separator itself
    fetchMock.mockResolvedValue(
      okStreamResponse([raw.slice(0, splitPoint), raw.slice(splitPoint)]),
    );

    const onStart = vi.fn();
    await streamChat({ history: [{ role: "user", content: "hi" }] }, { onStart });

    expect(onStart).toHaveBeenCalledWith("conv-2");
  });

  it("reports a mid-stream error event through onError without throwing", async () => {
    fetchMock.mockResolvedValue(
      okStreamResponse([sse({ type: "error", error: "answer generation failed" })]),
    );

    const onError = vi.fn();
    await expect(
      streamChat({ history: [{ role: "user", content: "hi" }] }, { onError }),
    ).resolves.toBeUndefined();
    expect(onError).toHaveBeenCalledWith("answer generation failed");
  });

  it("throws ChatRequestError when the response is not ok", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ error: "invalid or missing API key" }), { status: 401 }),
    );

    await expect(
      streamChat({ history: [{ role: "user", content: "hi" }] }, {}),
    ).rejects.toMatchObject({ message: "invalid or missing API key", status: 401 });
  });

  it("throws ChatRequestError when fetch itself rejects", async () => {
    fetchMock.mockRejectedValue(new Error("network down"));

    await expect(
      streamChat({ history: [{ role: "user", content: "hi" }] }, {}),
    ).rejects.toMatchObject({ message: "network down", status: 0 });
  });

  it("notifies onUnauthorized listeners exactly once on a 401, and not on other error statuses", async () => {
    const listener = vi.fn();
    const unsubscribe = onUnauthorized(listener);

    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ error: "invalid token" }), { status: 401 }),
    );
    await expect(streamChat({ history: [{ role: "user", content: "hi" }] }, {})).rejects.toThrow();
    expect(listener).toHaveBeenCalledTimes(1);

    fetchMock.mockResolvedValue(new Response(JSON.stringify({ error: "rate limited" }), { status: 429 }));
    await expect(streamChat({ history: [{ role: "user", content: "hi" }] }, {})).rejects.toThrow();
    expect(listener).toHaveBeenCalledTimes(1);

    unsubscribe();
  });

  it("stops notifying an unsubscribed onUnauthorized listener", async () => {
    const listener = vi.fn();
    const unsubscribe = onUnauthorized(listener);
    unsubscribe();

    fetchMock.mockResolvedValue(new Response(JSON.stringify({ error: "invalid token" }), { status: 401 }));
    await expect(streamChat({ history: [{ role: "user", content: "hi" }] }, {})).rejects.toThrow();

    expect(listener).not.toHaveBeenCalled();
  });
});

describe("sendFeedback", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    getTokenMock.mockReset();
    getTokenMock.mockReturnValue(null);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("resolves with the backend body on success", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    const result = await sendFeedback("trace-1", 1);

    expect(result).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/chat/trace-1/feedback",
      expect.objectContaining({ method: "PATCH" }),
    );
  });

  it("attaches the Authorization bearer header when a token is present", async () => {
    getTokenMock.mockReturnValue("jwt-abc123");
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    await sendFeedback("trace-1", 1);

    const [, init] = fetchMock.mock.calls[0];
    expect((init.headers as Record<string, string>).authorization).toBe("Bearer jwt-abc123");
  });

  it("omits the Authorization header when no token is present", async () => {
    getTokenMock.mockReturnValue(null);
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    await sendFeedback("trace-1", 1);

    const [, init] = fetchMock.mock.calls[0];
    expect((init.headers as Record<string, string>).authorization).toBeUndefined();
  });

  it("throws ChatRequestError on a non-ok response", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ error: "rate limited" }), { status: 429 }),
    );

    await expect(sendFeedback("trace-1", -1)).rejects.toMatchObject({
      message: "rate limited",
      status: 429,
    });
  });
});
