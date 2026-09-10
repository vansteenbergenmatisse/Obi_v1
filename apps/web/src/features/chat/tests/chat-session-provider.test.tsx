/**
 * ChatSessionProvider / useChatSession — PLAN 4.7.2's extraction of ChatPanel's inline
 * conversation state into a shared context (architecture decision D0, so the widget and the
 * full-page panel can read one live session in 4.7.4). This test targets `restart()`
 * specifically — the one genuinely new piece of behavior this extraction adds; streaming/
 * citation/feedback/abort behavior is already locked in by `chat-panel.test.tsx`.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ChatStreamEvent } from "@omniboost/contracts";
import type { SentImage } from "../model/messages";

const { captureWidgetAccessTokenMock } = vi.hoisted(() => ({
  captureWidgetAccessTokenMock: vi.fn(),
}));

// `chat-client.ts` (exercised for real, not mocked, by these tests) also imports this module
// for `getWidgetAccessToken` — both exports must stay present or its fetch calls will throw.
vi.mock("../api/access-token", () => ({
  captureWidgetAccessToken: captureWidgetAccessTokenMock,
  getWidgetAccessToken: () => null,
}));

import { ChatSessionProvider, useChatSession } from "../ui/chat-session-provider";

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

function Harness() {
  const { messages, pending, sendMessage, restart } = useChatSession();
  return (
    <div>
      <button onClick={() => sendMessage("hi")}>send</button>
      <button onClick={() => restart()}>restart</button>
      <div data-testid="pending">{String(pending)}</div>
      <div data-testid="count">{messages.length}</div>
    </div>
  );
}

describe("ChatSessionProvider", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    captureWidgetAccessTokenMock.mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("captures the widget access token once on mount", () => {
    render(
      <ChatSessionProvider>
        <Harness />
      </ChatSessionProvider>,
    );

    expect(captureWidgetAccessTokenMock).toHaveBeenCalledTimes(1);
  });

  it("shows an actionable message when the access token is rejected (401)", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ error: "unauthorized" }), { status: 401 }),
    );

    function ErrorHarness() {
      const { messages, sendMessage } = useChatSession();
      const assistant = messages.find((m) => m.role === "assistant");
      return (
        <div>
          <button onClick={() => sendMessage("hi")}>send</button>
          <div data-testid="error-text">{assistant?.text ?? ""}</div>
        </div>
      );
    }

    render(
      <ChatSessionProvider>
        <ErrorHarness />
      </ChatSessionProvider>,
    );

    await userEvent.click(screen.getByText("send"));
    await waitFor(() =>
      expect(screen.getByTestId("error-text").textContent).toBe(
        "Your access link has expired — open the chat from your invite link again.",
      ),
    );
  });

  it("clears messages and pending state", async () => {
    fetchMock.mockResolvedValue(
      okStreamResponse([
        sse({ type: "start", conversationId: "conv-1" }),
        sse({ type: "done", answer: "hello", citations: [], traceId: "trace-1", refused: false }),
      ]),
    );

    render(
      <ChatSessionProvider>
        <Harness />
      </ChatSessionProvider>,
    );

    await userEvent.click(screen.getByText("send"));
    await waitFor(() => expect(screen.getByTestId("count").textContent).toBe("2"));

    await userEvent.click(screen.getByText("restart"));

    expect(screen.getByTestId("count").textContent).toBe("0");
    expect(screen.getByTestId("pending").textContent).toBe("false");
  });

  it("aborts an in-flight stream instead of letting it resurrect the cleared thread", async () => {
    let capturedSignal: AbortSignal | undefined;
    fetchMock.mockImplementation((_url: string, init?: RequestInit) => {
      capturedSignal = init?.signal ?? undefined;
      return new Promise(() => {
        /* never resolves — restart happens while this request is still in flight */
      });
    });

    render(
      <ChatSessionProvider>
        <Harness />
      </ChatSessionProvider>,
    );

    await userEvent.click(screen.getByText("send"));
    await waitFor(() => expect(capturedSignal).toBeDefined());

    await userEvent.click(screen.getByText("restart"));

    expect(capturedSignal?.aborted).toBe(true);
    expect(screen.getByTestId("count").textContent).toBe("0");
  });

  it("sends the configured knowledgeScope on the outgoing request", async () => {
    let requestBody: unknown;
    fetchMock.mockImplementation((_url: string, init?: RequestInit) => {
      requestBody = init?.body ? JSON.parse(init.body as string) : undefined;
      return Promise.resolve(
        okStreamResponse([
          sse({ type: "start", conversationId: "conv-1" }),
          sse({ type: "done", answer: "hi", citations: [], traceId: "trace-1", refused: false }),
        ]),
      );
    });

    render(
      <ChatSessionProvider knowledgeScope="obi-mews-test">
        <Harness />
      </ChatSessionProvider>,
    );

    await userEvent.click(screen.getByText("send"));
    await waitFor(() => expect(requestBody).toBeDefined());

    expect((requestBody as { knowledgeScope?: string }).knowledgeScope).toBe("obi-mews-test");
  });

  it("applies a runtime scope change (the PLAN 10.8 switcher) to the next outgoing request", async () => {
    let requestBody: unknown;
    fetchMock.mockImplementation((_url: string, init?: RequestInit) => {
      requestBody = init?.body ? JSON.parse(init.body as string) : undefined;
      return Promise.resolve(
        okStreamResponse([
          sse({ type: "start", conversationId: "conv-1" }),
          sse({ type: "done", answer: "hi", citations: [], traceId: "trace-1", refused: false }),
        ]),
      );
    });

    function ScopeHarness() {
      const { sendMessage, knowledgeScope, setKnowledgeScope } = useChatSession();
      return (
        <div>
          <div data-testid="scope">{knowledgeScope ?? "none"}</div>
          <button onClick={() => setKnowledgeScope("obi-toast-test")}>set-toast</button>
          <button onClick={() => sendMessage("hi")}>send</button>
        </div>
      );
    }

    render(
      <ChatSessionProvider knowledgeScope="obi-mews-test">
        <ScopeHarness />
      </ChatSessionProvider>,
    );

    // Seeded from the embed's prop, then overridden live by the switcher.
    expect(screen.getByTestId("scope").textContent).toBe("obi-mews-test");
    await userEvent.click(screen.getByText("set-toast"));
    expect(screen.getByTestId("scope").textContent).toBe("obi-toast-test");

    await userEvent.click(screen.getByText("send"));
    await waitFor(() => expect(requestBody).toBeDefined());
    expect((requestBody as { knowledgeScope?: string }).knowledgeScope).toBe("obi-toast-test");
  });

  it("omits knowledgeScope from the outgoing request when not configured", async () => {
    let requestBody: unknown;
    fetchMock.mockImplementation((_url: string, init?: RequestInit) => {
      requestBody = init?.body ? JSON.parse(init.body as string) : undefined;
      return Promise.resolve(
        okStreamResponse([
          sse({ type: "start", conversationId: "conv-1" }),
          sse({ type: "done", answer: "hi", citations: [], traceId: "trace-1", refused: false }),
        ]),
      );
    });

    render(
      <ChatSessionProvider>
        <Harness />
      </ChatSessionProvider>,
    );

    await userEvent.click(screen.getByText("send"));
    await waitFor(() => expect(requestBody).toBeDefined());

    expect((requestBody as { knowledgeScope?: string }).knowledgeScope).toBeUndefined();
  });

  it("attaches images to the newest history turn only, and reads imageAnalysis back off done", async () => {
    const image: SentImage = {
      mediaType: "image/png",
      data: "ZmFrZS1ieXRlcw==",
      previewUrl: "blob:mock-url",
      alt: "screenshot.png",
    };
    let requestBody: unknown;
    fetchMock.mockImplementation((_url: string, init?: RequestInit) => {
      requestBody = init?.body ? JSON.parse(init.body as string) : undefined;
      return Promise.resolve(
        okStreamResponse([
          sse({ type: "start", conversationId: "conv-1" }),
          sse({
            type: "done",
            answer: "there's a dashboard",
            citations: [],
            traceId: "trace-1",
            refused: false,
            imageAnalysis: "The screenshot shows a dashboard with three charts.",
          }),
        ]),
      );
    });

    function ImageHarness() {
      const { messages, sendMessage } = useChatSession();
      const assistant = messages.find((m) => m.role === "assistant");
      return (
        <div>
          <button onClick={() => sendMessage("what is this?", [image])}>send</button>
          <div data-testid="image-analysis">{assistant?.imageAnalysis ?? ""}</div>
        </div>
      );
    }

    render(
      <ChatSessionProvider>
        <ImageHarness />
      </ChatSessionProvider>,
    );

    await userEvent.click(screen.getByText("send"));
    await waitFor(() =>
      expect(screen.getByTestId("image-analysis").textContent).toBe(
        "The screenshot shows a dashboard with three charts.",
      ),
    );

    const history = (requestBody as { history: Array<Record<string, unknown>> }).history;
    expect(history).toHaveLength(1);
    expect(history[0]).toMatchObject({
      role: "user",
      content: "what is this?",
      images: [{ mediaType: "image/png", data: "ZmFrZS1ieXRlcw==" }],
    });
  });

  it("marks a turn as clarifying (not refused) and keeps its options, per ADR-0008 decision 3", async () => {
    fetchMock.mockResolvedValue(
      okStreamResponse([
        sse({ type: "start", conversationId: "conv-1" }),
        sse({
          type: "done",
          answer: "Which kind of limit do you mean: expense or approval?",
          citations: [],
          traceId: null,
          refused: false,
          needsClarification: true,
          clarificationQuestion: "Which kind of limit do you mean: expense or approval?",
          clarificationOptions: ["Expense limits", "Approval thresholds"],
        }),
      ]),
    );

    function ClarifyHarness() {
      const { messages, sendMessage } = useChatSession();
      const assistant = messages.find((m) => m.role === "assistant");
      return (
        <div>
          <button onClick={() => sendMessage("what are the limits?")}>send</button>
          <div data-testid="status">{assistant?.status ?? ""}</div>
          <div data-testid="options">{(assistant?.clarificationOptions ?? []).join(",")}</div>
        </div>
      );
    }

    render(
      <ChatSessionProvider>
        <ClarifyHarness />
      </ChatSessionProvider>,
    );

    await userEvent.click(screen.getByText("send"));
    await waitFor(() => expect(screen.getByTestId("status").textContent).toBe("clarifying"));
    expect(screen.getByTestId("options").textContent).toBe("Expense limits,Approval thresholds");
  });

  it("resends a clarifying turn's question as history on the next message", async () => {
    const requestBodies: unknown[] = [];
    fetchMock.mockImplementation((_url: string, init?: RequestInit) => {
      requestBodies.push(init?.body ? JSON.parse(init.body as string) : undefined);
      const isFirst = requestBodies.length === 1;
      return Promise.resolve(
        okStreamResponse([
          sse({ type: "start", conversationId: "conv-1" }),
          isFirst
            ? sse({
                type: "done",
                answer: "Which kind of limit?",
                citations: [],
                traceId: null,
                refused: false,
                needsClarification: true,
                clarificationOptions: ["Expense limits", "Approval thresholds"],
              })
            : sse({ type: "done", answer: "Expense limits are $500.", citations: [], traceId: "trace-2", refused: false }),
        ]),
      );
    });

    render(
      <ChatSessionProvider>
        <Harness />
      </ChatSessionProvider>,
    );

    await userEvent.click(screen.getByText("send"));
    await waitFor(() => expect(screen.getByTestId("count").textContent).toBe("2"));
    await userEvent.click(screen.getByText("send"));
    await waitFor(() => expect(screen.getByTestId("count").textContent).toBe("4"));

    const secondHistory = (requestBodies[1] as { history: Array<Record<string, unknown>> }).history;
    expect(secondHistory).toHaveLength(3);
    expect(secondHistory[1]).toMatchObject({ role: "assistant", content: "Which kind of limit?" });
  });
});
