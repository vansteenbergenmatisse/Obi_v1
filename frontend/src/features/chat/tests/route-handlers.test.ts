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

// panel w-proxy · substep p0-s0_5-reg-the-widget — "Path" check: the two app router entry files
// must route to the right handlers. Stubbing the feature barrel (rather than importing it for
// real) keeps this a pure wiring assertion and avoids pulling the barrel's unrelated React UI
// exports into this node-environment (*.test.ts) file.
const { handlePostChatSpy, handlePatchFeedbackSpy } = vi.hoisted(() => ({
  handlePostChatSpy: vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 })),
  handlePatchFeedbackSpy: vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 })),
}));

vi.mock("@/features/chat", () => ({
  handlePostChat: handlePostChatSpy,
  handlePatchFeedback: handlePatchFeedbackSpy,
}));

import { AutomationApiConfigError } from "@/platform/automation-api";
import { handlePatchFeedback, handlePostChat } from "../server/route-handlers";
import { POST as postChatRoute } from "@/app/api/chat/route";
import { PATCH as patchFeedbackRoute } from "@/app/api/chat/[traceId]/feedback/route";

const FAKE_CONFIG = { baseUrl: "http://backend.internal", apiKey: "secret", timeoutMs: 1000 };

function jsonRequest(body: unknown, headers: Record<string, string> = {}): Request {
  return new Request("http://localhost/api/chat", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...headers,
    },
    body: JSON.stringify(body),
  });
}

function feedbackRequest(body: unknown, headers: Record<string, string> = {}): Request {
  return new Request("http://localhost/api/chat/trace-1/feedback", {
    method: "PATCH",
    headers: {
      "content-type": "application/json",
      ...headers,
    },
    body: JSON.stringify(body),
  });
}

beforeEach(() => {
  callAutomationApiMock.mockReset();
  readAutomationApiConfigMock.mockReset();
  readAutomationApiConfigMock.mockReturnValue(FAKE_CONFIG);
  handlePostChatSpy.mockClear();
  handlePatchFeedbackSpy.mockClear();
});

describe("proxy route wiring (panel w-proxy · substep p0-s0_5-reg-the-widget)", () => {
  // panel w-proxy · substep p0-s0_5-reg-the-widget
  // "Path: /api/chat ... route to the right handlers" — the thin app-router entry composes
  // the feature's handlePostChat, not a copy or a reimplementation.
  it("w_proxy_post_chat_route_wires_to_handle_post_chat", async () => {
    const request = new Request("http://localhost/api/chat", { method: "POST" });

    const response = await postChatRoute(request);

    expect(handlePostChatSpy).toHaveBeenCalledTimes(1);
    expect(handlePostChatSpy).toHaveBeenCalledWith(request);
    expect(response.status).toBe(200);
  });

  // panel w-proxy · substep p0-s0_5-reg-the-widget
  // "Path: ... /api/chat/{traceId}/feedback (both routes exist and route to the right
  // handlers)" — the dynamic segment is unwrapped and threaded to handlePatchFeedback verbatim.
  it("w_proxy_feedback_route_wires_to_handle_patch_feedback_with_trace_id", async () => {
    const request = new Request("http://localhost/api/chat/trace-99/feedback", { method: "PATCH" });

    const response = await patchFeedbackRoute(request as never, {
      params: Promise.resolve({ traceId: "trace-99" }),
    });

    expect(handlePatchFeedbackSpy).toHaveBeenCalledTimes(1);
    expect(handlePatchFeedbackSpy).toHaveBeenCalledWith(request, "trace-99");
    expect(response.status).toBe(200);
  });
});

describe("handlePostChat", () => {
  it("rejects malformed JSON before calling the backend", async () => {
    const request = new Request("http://localhost/api/chat", {
      method: "POST",
      headers: {},
      body: "{not json",
    });
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

  // panel r1-proxy · substep p0-s0_5-reg-retrieval-stage-1
  // The proxy must stream the SSE bytes back unbuffered: bytes must be readable from the
  // returned Response's body before the upstream source stream closes, not only after.
  it("r1_proxy_streams_sse_bytes_back_unbuffered", async () => {
    let sourceController!: ReadableStreamDefaultController<Uint8Array>;
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        sourceController = controller;
      },
    });
    callAutomationApiMock.mockResolvedValue(
      new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }),
    );

    const request = jsonRequest({ history: [{ role: "user", content: "hi" }] });
    const responsePromise = handlePostChat(request);

    // Enqueue one chunk and deliberately leave the source stream open (never closed).
    sourceController.enqueue(new TextEncoder().encode("data: {\"type\":\"start\"}\n\n"));

    const response = await responsePromise;
    expect(response.body).not.toBeNull();

    const reader = response.body!.getReader();
    const { value, done } = await reader.read();

    // If the proxy buffered the whole stream before responding, this read would hang forever
    // (the source is still open) instead of resolving with the first chunk.
    expect(done).toBe(false);
    expect(new TextDecoder().decode(value)).toContain("start");

    sourceController.close();
  });

  it("w_proxy_streams_bytes_back_unbuffered", async () => {
    // panel w-proxy · substep p0-s0_5-reg-the-widget
    // "Streams: a byte passthrough, no buffering" — re-proves the same fact under the
    // widget panel's own name (see r1_proxy_streams_sse_bytes_back_unbuffered above, which
    // proves it for panel r1-proxy).
    let sourceController!: ReadableStreamDefaultController<Uint8Array>;
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        sourceController = controller;
      },
    });
    callAutomationApiMock.mockResolvedValue(
      new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }),
    );

    const request = jsonRequest({ history: [{ role: "user", content: "hi" }] });
    const responsePromise = handlePostChat(request);

    // Enqueue one chunk and deliberately leave the source stream open (never closed).
    sourceController.enqueue(new TextEncoder().encode("data: {\"type\":\"start\"}\n\n"));

    const response = await responsePromise;
    expect(response.body).not.toBeNull();

    const reader = response.body!.getReader();
    const { value, done } = await reader.read();

    // If the proxy buffered the whole stream before responding, this read would hang forever
    // (the source is still open) instead of resolving with the first chunk.
    expect(done).toBe(false);
    expect(new TextDecoder().decode(value)).toContain("start");

    sourceController.close();
  });

  it("forwards knowledgeScope unmodified as knowledge_scope", async () => {
    callAutomationApiMock.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    const request = jsonRequest({
      knowledgeScope: "mews",
      history: [{ role: "user", content: "hi" }],
    });
    await handlePostChat(request);

    expect(callAutomationApiMock).toHaveBeenCalledWith(
      FAKE_CONFIG,
      expect.objectContaining({ body: expect.objectContaining({ knowledge_scope: "mews" }) }),
    );
  });

  it("forwards the backend's error status and body verbatim", async () => {
    callAutomationApiMock.mockResolvedValue(
      new Response(JSON.stringify({ error: "rate limited" }), { status: 429 }),
    );

    const response = await handlePostChat(jsonRequest({ history: [{ role: "user", content: "hi" }] }));

    expect(response.status).toBe(429);
    expect(await response.json()).toEqual({ error: "rate limited" });
  });

  // panel w-proxy · substep p0-s0_5-reg-the-widget
  // "Checks: structural shape only; the backend owns the business caps and its 400 is
  // forwarded as-is" — a business-rule 400 (e.g. an unknown knowledge_scope, which this proxy
  // only checks for shape/membership per CLAUDE.md rule 2) reaches the browser unmodified, not
  // swallowed or reshaped into a generic error.
  it("w_proxy_forwards_backend_400_as_is_without_reshaping", async () => {
    const backendBody = { error: "unknown knowledge_scope value", detail: "scope not in tag map" };
    callAutomationApiMock.mockResolvedValue(new Response(JSON.stringify(backendBody), { status: 400 }));

    const response = await handlePostChat(jsonRequest({ history: [{ role: "user", content: "hi" }] }));

    expect(response.status).toBe(400);
    expect(await response.json()).toEqual(backendBody);
  });

  // panel w-proxy · substep p0-s0_5-reg-the-widget
  // "Adds: the server key from the Next.js server environment; never exposed to the browser" —
  // the second half of that check (the first half, that the key is attached server-side to the
  // outbound backend call, is proven by platform/automation-api/tests/client.test.ts's
  // r1_proxy_forwards_chat_api_key_as_bearer_auth). Here: nothing the proxy hands back to the
  // browser — headers or body — ever contains the configured host secret.
  it("w_proxy_never_exposes_the_server_key_to_the_browser", async () => {
    callAutomationApiMock.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    const response = await handlePostChat(jsonRequest({ history: [{ role: "user", content: "hi" }] }));

    expect(response.headers.get("authorization")).toBeNull();
    const responseText = await response.clone().text();
    const serializedHeaders = JSON.stringify([...response.headers.entries()]);
    expect(serializedHeaders).not.toContain(FAKE_CONFIG.apiKey);
    expect(responseText).not.toContain(FAKE_CONFIG.apiKey);
  });

  // panel ov-widget · substep p0-s0_5-reg-system-overview
  // System-overview step 3: "The proxy adds the server key and streams the answer back." One
  // composite proxy-hop assertion: (a) the outbound backend call is issued through the
  // server-side-configured client that carries the host key (FAKE_CONFIG.apiKey — read only on the
  // server, injected by callAutomationApi as its Bearer auth; see client.test.ts's
  // r1_proxy_forwards_chat_api_key_as_bearer_auth for the header itself), (b) the backend's SSE
  // body is streamed straight back to the browser, and (c) that host key never appears in anything
  // the browser receives (headers or body).
  it("ov_widget_proxy_adds_the_server_key_and_streams_the_answer_back", async () => {
    let sourceController!: ReadableStreamDefaultController<Uint8Array>;
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        sourceController = controller;
      },
    });
    callAutomationApiMock.mockResolvedValue(
      new Response(stream, { status: 200, headers: { "content-type": "text/event-stream" } }),
    );

    const request = jsonRequest({ history: [{ role: "user", content: "how do I refund a folio?" }] });
    const responsePromise = handlePostChat(request);

    sourceController.enqueue(new TextEncoder().encode("data: {\"type\":\"token\",\"delta\":\"Go to\"}\n\n"));
    const response = await responsePromise;

    // (a) The outbound call went through the server-side client holding the host key.
    expect(callAutomationApiMock).toHaveBeenCalledWith(
      FAKE_CONFIG,
      expect.objectContaining({ path: "/chat", method: "POST" }),
    );
    expect(FAKE_CONFIG.apiKey).toBe("secret");

    // (b) The answer streams back — the first chunk is readable before the source stream closes.
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("text/event-stream");
    const reader = response.body!.getReader();
    const { value, done } = await reader.read();
    expect(done).toBe(false);
    expect(new TextDecoder().decode(value)).toContain("Go to");

    // (c) The browser never sees the host key — not in headers, not in the body.
    const serializedHeaders = JSON.stringify([...response.headers.entries()]);
    expect(serializedHeaders).not.toContain(FAKE_CONFIG.apiKey);

    sourceController.close();
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

  // PLAN 11.1c (ADR-0014): the pilot invite-token gate is retired. The incoming `Authorization`
  // header (the embed frame's platform-signed JWT) is threaded through to `callAutomationApi` as
  // `userToken` — never forwarded as the outbound `Authorization` (that stays the host key).
  it("threads a Bearer Authorization header through to callAutomationApi as userToken", async () => {
    callAutomationApiMock.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    const request = jsonRequest(
      { history: [{ role: "user", content: "hi" }] },
      { authorization: "Bearer JWT123" },
    );
    await handlePostChat(request);

    expect(callAutomationApiMock).toHaveBeenCalledWith(
      FAKE_CONFIG,
      expect.objectContaining({ userToken: "JWT123" }),
    );
  });

  it("passes no userToken when the request carries no Authorization header", async () => {
    callAutomationApiMock.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    const request = jsonRequest({ history: [{ role: "user", content: "hi" }] });
    await handlePostChat(request);

    const [, callArgs] = callAutomationApiMock.mock.calls[0] as [unknown, { userToken?: string }];
    expect(callArgs.userToken).toBeUndefined();
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
