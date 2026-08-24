import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ChatStreamEvent } from "@omniboost/contracts";

const { getWidgetAccessTokenMock } = vi.hoisted(() => ({
  getWidgetAccessTokenMock: vi.fn(),
}));

vi.mock("../api/access-token", () => ({
  getWidgetAccessToken: getWidgetAccessTokenMock,
}));

import { sendFeedback, streamChat } from "../api/chat-client";

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
    getWidgetAccessTokenMock.mockReset();
    getWidgetAccessTokenMock.mockReturnValue(null);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("attaches the access token header when one is present", async () => {
    getWidgetAccessTokenMock.mockReturnValue("invite-abc123");
    fetchMock.mockResolvedValue(okStreamResponse([sse({ type: "start", conversationId: "c" })]));

    await streamChat({ history: [{ role: "user", content: "hi" }] }, {});

    const [, init] = fetchMock.mock.calls[0];
    expect((init.headers as Record<string, string>)["x-widget-access-token"]).toBe("invite-abc123");
  });

  it("omits the access token header when none is present", async () => {
    getWidgetAccessTokenMock.mockReturnValue(null);
    fetchMock.mockResolvedValue(okStreamResponse([sse({ type: "start", conversationId: "c" })]));

    await streamChat({ history: [{ role: "user", content: "hi" }] }, {});

    const [, init] = fetchMock.mock.calls[0];
    expect((init.headers as Record<string, string>)["x-widget-access-token"]).toBeUndefined();
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
});

describe("sendFeedback", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    getWidgetAccessTokenMock.mockReset();
    getWidgetAccessTokenMock.mockReturnValue(null);
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

  it("attaches the access token header when one is present", async () => {
    getWidgetAccessTokenMock.mockReturnValue("invite-abc123");
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    await sendFeedback("trace-1", 1);

    const [, init] = fetchMock.mock.calls[0];
    expect((init.headers as Record<string, string>)["x-widget-access-token"]).toBe("invite-abc123");
  });

  it("omits the access token header when none is present", async () => {
    getWidgetAccessTokenMock.mockReturnValue(null);
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    await sendFeedback("trace-1", 1);

    const [, init] = fetchMock.mock.calls[0];
    expect((init.headers as Record<string, string>)["x-widget-access-token"]).toBeUndefined();
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
