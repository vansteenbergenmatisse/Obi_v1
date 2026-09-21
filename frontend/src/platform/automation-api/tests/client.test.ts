import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { callAutomationApi } from "../client";

const FAKE_CONFIG = { baseUrl: "http://backend.internal", apiKey: "fake-chat-api-key", timeoutMs: 1000 };

describe("callAutomationApi", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // panel r1-proxy · substep 0.5.3
  // "Proxy adds: Authorization: Bearer CHAT_API_KEY" — the outbound Authorization header
  // carries the configured host secret, never the end-user's own token.
  it("r1_proxy_forwards_chat_api_key_as_bearer_auth", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    await callAutomationApi(FAKE_CONFIG, {
      path: "/chat",
      method: "POST",
      body: { history: [] },
      userToken: "end-user-jwt-should-not-appear-here",
    });

    const [, init] = fetchMock.mock.calls[0];
    const headers = init.headers as Record<string, string>;
    expect(headers.authorization).toBe(`Bearer ${FAKE_CONFIG.apiKey}`);
    expect(headers.authorization).not.toContain("end-user-jwt-should-not-appear-here");
  });

  // panel r1-proxy · substep 0.5.3
  // "forwards the body as-is" — the request body reaches the backend call untouched.
  it("forwards the request body as-is to the backend call", async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    const body = { conversation_id: "conv-1", history: [{ role: "user", content: "hi" }] };
    await callAutomationApi(FAKE_CONFIG, { path: "/chat", method: "POST", body });

    const [, init] = fetchMock.mock.calls[0];
    expect(init.body).toBe(JSON.stringify(body));
  });
});
