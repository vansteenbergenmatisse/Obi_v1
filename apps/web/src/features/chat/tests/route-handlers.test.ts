import { beforeEach, describe, expect, it, vi } from "vitest";

const { callAutomationApiMock, readAutomationApiConfigMock } = vi.hoisted(() => ({
  callAutomationApiMock: vi.fn(),
  readAutomationApiConfigMock: vi.fn(),
}));

vi.mock("@/platform/automation-api", () => ({
  callAutomationApi: callAutomationApiMock,
  readAutomationApiConfig: readAutomationApiConfigMock,
  AutomationApiConfigError: class AutomationApiConfigError extends Error {},
}));

import { AutomationApiConfigError } from "@/platform/automation-api";
import { handlePatchFeedback, handlePostChat } from "../server/route-handlers";

const FAKE_CONFIG = { baseUrl: "http://backend.internal", apiKey: "secret", timeoutMs: 1000 };

function jsonRequest(body: unknown, headers: Record<string, string> = {}): Request {
  return new Request("http://localhost/api/chat", {
    method: "POST",
    headers: { "content-type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
}

function feedbackRequest(body: unknown): Request {
  return new Request("http://localhost/api/chat/trace-1/feedback", {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

beforeEach(() => {
  callAutomationApiMock.mockReset();
  readAutomationApiConfigMock.mockReset();
  readAutomationApiConfigMock.mockReturnValue(FAKE_CONFIG);
});

describe("handlePostChat", () => {
  it("rejects malformed JSON before calling the backend", async () => {
    const request = new Request("http://localhost/api/chat", { method: "POST", body: "{not json" });
    const response = await handlePostChat(request);
    expect(response.status).toBe(400);
    expect(callAutomationApiMock).not.toHaveBeenCalled();
  });

  it("rejects a request missing history before calling the backend", async () => {
    const response = await handlePostChat(jsonRequest({}));
    expect(response.status).toBe(400);
    expect(callAutomationApiMock).not.toHaveBeenCalled();
  });

  it("fails closed with 503 when the automation API is unconfigured", async () => {
    readAutomationApiConfigMock.mockImplementation(() => {
      throw new AutomationApiConfigError("CHAT_API_KEY is not configured");
    });

    const response = await handlePostChat(jsonRequest({ history: [{ role: "user", content: "hi" }] }));

    expect(response.status).toBe(503);
    expect(callAutomationApiMock).not.toHaveBeenCalled();
  });

  it("translates the request, forwards the idempotency header, and streams the backend body through", async () => {
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("data: {}\n\n"));
        controller.close();
      },
    });
    callAutomationApiMock.mockResolvedValue(
      new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }),
    );

    const request = jsonRequest(
      { conversationId: "conv-1", principal: "user-1", history: [{ role: "user", content: "hi" }] },
      { "idempotency-key": "abc-123" },
    );
    const response = await handlePostChat(request);

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("text/event-stream");
    expect(callAutomationApiMock).toHaveBeenCalledWith(FAKE_CONFIG, {
      path: "/chat",
      method: "POST",
      body: {
        conversation_id: "conv-1",
        history: [{ role: "user", content: "hi" }],
        principal: "user-1",
      },
      idempotencyKey: "abc-123",
    });
  });

  it("forwards the backend's error status and body verbatim", async () => {
    callAutomationApiMock.mockResolvedValue(
      new Response(JSON.stringify({ error: "rate limited" }), { status: 429 }),
    );

    const response = await handlePostChat(jsonRequest({ history: [{ role: "user", content: "hi" }] }));

    expect(response.status).toBe(429);
    expect(await response.json()).toEqual({ error: "rate limited" });
  });

  it("returns 502 when the upstream call itself fails", async () => {
    callAutomationApiMock.mockRejectedValue(new Error("connection refused"));

    const response = await handlePostChat(jsonRequest({ history: [{ role: "user", content: "hi" }] }));

    expect(response.status).toBe(502);
  });

  it("does not 413 a legitimate image-bearing turn within the backend's own image caps", async () => {
    // 4 images (chat_max_images_per_turn) at ~5MB raw each (chat_max_image_bytes), base64-encoded —
    // the real-world ceiling this proxy must admit so the backend's own caps stay authoritative.
    const oneImageBase64 = "A".repeat(Math.ceil((5_000_000 * 4) / 3));
    const images = Array.from({ length: 4 }, () => ({ mediaType: "image/png", data: oneImageBase64 }));
    callAutomationApiMock.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    const response = await handlePostChat(
      jsonRequest({ history: [{ role: "user", content: "what's in these?", images }] }),
    );

    expect(response.status).toBe(200);
    expect(callAutomationApiMock).toHaveBeenCalled();
  });

  it("still rejects a pathologically oversized body with 413 before calling the backend", async () => {
    const hugeBase64 = "A".repeat(60_000_000);
    const request = jsonRequest({
      history: [{ role: "user", content: "hi", images: [{ mediaType: "image/png", data: hugeBase64 }] }],
    });

    const response = await handlePostChat(request);

    expect(response.status).toBe(413);
    expect(await response.json()).toEqual({ error: "request body too large" });
    expect(callAutomationApiMock).not.toHaveBeenCalled();
  });
});

describe("handlePatchFeedback", () => {
  it("rejects an invalid feedback value before calling the backend", async () => {
    const response = await handlePatchFeedback(feedbackRequest({ feedback: 0 }), "trace-1");
    expect(response.status).toBe(400);
    expect(callAutomationApiMock).not.toHaveBeenCalled();
  });

  it("fails closed with 503 when the automation API is unconfigured", async () => {
    readAutomationApiConfigMock.mockImplementation(() => {
      throw new AutomationApiConfigError("CHAT_API_KEY is not configured");
    });

    const response = await handlePatchFeedback(feedbackRequest({ feedback: 1 }), "trace-1");

    expect(response.status).toBe(503);
  });

  it("forwards to the backend with an encoded traceId and a shortened timeout", async () => {
    callAutomationApiMock.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    const response = await handlePatchFeedback(feedbackRequest({ feedback: 1 }), "trace/1");

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ ok: true });
    expect(callAutomationApiMock).toHaveBeenCalledWith(
      { ...FAKE_CONFIG, timeoutMs: 15_000 },
      { path: "/chat/trace%2F1/feedback", method: "PATCH", body: { feedback: 1 } },
    );
  });
});
