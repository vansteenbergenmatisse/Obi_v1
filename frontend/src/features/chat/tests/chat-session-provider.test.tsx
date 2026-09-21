/**
 * ChatSessionProvider / useChatSession — PLAN 4.7.2's extraction of ChatPanel's inline
 * conversation state into a shared context (architecture decision D0, so the widget and the
 * full-page panel can read one live session in 4.7.4). This test targets `restart()`
 * specifically — the one genuinely new piece of behavior this extraction adds; streaming/
 * citation/feedback/abort behavior is already locked in by `chat-panel.test.tsx`.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ChatStreamEvent } from "@omniboost/contracts";
import type { SentImage } from "../model/messages";

// `chat-client.ts` (exercised for real, not mocked, by these tests) reads the embed token via
// `@/features/embed`'s `getToken` — stubbed to "no token" so these tests exercise the tokenless/
// default-app-shell path, matching this provider's pre-PLAN-11.1c behavior.
vi.mock("@/features/embed", () => ({
  getToken: () => null,
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
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("surfaces the backend's error message on a rejected (401) request", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ error: "invalid token" }), { status: 401 }),
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
    await waitFor(() => expect(screen.getByTestId("error-text").textContent).toBe("invalid token"));
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

  it("ov_widget_embedded_with_scope_from_its_mount_config", async () => {
    // panel ov-widget · substep p0-s0_5-reg-system-overview
    // System-overview step 1: "The widget is embedded in a platform's page with a scope from its
    // config." The embedding page declares its platform scope once as the mount config
    // (`knowledgeScope` prop); when the user asks, that configured scope is what the widget's own
    // proxy request carries — the scope comes from the mount config, not from anything the user typed.
    let requestUrl: unknown;
    let requestBody: unknown;
    fetchMock.mockImplementation((url: string, init?: RequestInit) => {
      requestUrl = url;
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

    expect(requestUrl).toBe("/api/chat");
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

  it("w_scope_set_once_from_mount_prop_ignores_later_prop_changes", async () => {
    // panel w-scope · substep p0-s0_5-reg-the-widget
    // "Set: once, by the embedding page, as the knowledgeScope prop" — the session seeds its scope
    // from the prop only at mount (`useState(initialKnowledgeScope)`), it is never re-read from the
    // prop afterward. Prove that a later re-render with a *different* prop value does not change
    // what the next outgoing request carries; only the 10.8 dev switcher (`setKnowledgeScope`,
    // covered separately) can change it after mount.
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

    const { rerender } = render(
      <ChatSessionProvider knowledgeScope="obi-mews-test">
        <Harness />
      </ChatSessionProvider>,
    );

    // The embedding page re-renders with a different scope prop — this must NOT reach the session:
    // a real embed only ever sets this once, and the session must behave the same way.
    rerender(
      <ChatSessionProvider knowledgeScope="obi-toast-test">
        <Harness />
      </ChatSessionProvider>,
    );

    await userEvent.click(screen.getByText("send"));
    await waitFor(() => expect(requestBody).toBeDefined());

    expect((requestBody as { knowledgeScope?: string }).knowledgeScope).toBe("obi-mews-test");
  });

  it("w_scope_sent_on_every_outgoing_request_not_just_the_first", async () => {
    // panel w-scope · substep p0-s0_5-reg-the-widget
    // "Sent: on every request as knowledgeScope" — send two separate turns in the same session and
    // prove knowledgeScope rides on both request bodies, not only the first.
    const requestBodies: unknown[] = [];
    fetchMock.mockImplementation((_url: string, init?: RequestInit) => {
      requestBodies.push(init?.body ? JSON.parse(init.body as string) : undefined);
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
    await waitFor(() => expect(requestBodies).toHaveLength(1));
    await userEvent.click(screen.getByText("send"));
    await waitFor(() => expect(requestBodies).toHaveLength(2));

    expect((requestBodies[0] as { knowledgeScope?: string }).knowledgeScope).toBe("obi-mews-test");
    expect((requestBodies[1] as { knowledgeScope?: string }).knowledgeScope).toBe("obi-mews-test");
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

describe("ChatSessionProvider mount (panel w-panel · State)", () => {
  // Drift guard, same technique as `knowledge-scopes.test.ts`: rendering the real `(site)/layout.tsx`
  // (an `<html>`/`<body>` root layout) through Testing Library isn't representative of how Next
  // mounts it, so this asserts the actual source instead — deterministic, no DOM involved.
  const here = dirname(fileURLToPath(import.meta.url));
  // frontend/src/features/chat/tests → frontend/src/app
  const appDir = resolve(here, "../../../app");

  it("w_panel_state_one_chat_session_provider_mounted_once_in_the_sites_root_layout", () => {
    const siteLayoutSource = readFileSync(resolve(appDir, "(site)/layout.tsx"), "utf8");
    const mountCount = (siteLayoutSource.match(/<ChatSessionProvider\b/g) ?? []).length;
    expect(mountCount).toBe(1);
  });

  it("w_panel_state_other_root_layouts_do_not_mount_a_second_independent_session", () => {
    // The `/embed` frame and `/test-hosts/*` fake host pages are Next's "multiple root layouts"
    // siblings of `(site)/layout.tsx` (see its docstring) — neither may mount its own
    // `ChatSessionProvider` at the layout level, or the widget/full-page surfaces would read two
    // independent, contradictory conversations instead of the one PLAN 4.7.4 requires.
    const embedLayoutSource = readFileSync(resolve(appDir, "embed/layout.tsx"), "utf8");
    const testHostsLayoutSource = readFileSync(resolve(appDir, "test-hosts/layout.tsx"), "utf8");
    // Match only a JSX mount (`<ChatSessionProvider`), not the surrounding docstrings' prose
    // mentions of the name.
    expect(embedLayoutSource).not.toMatch(/<ChatSessionProvider\b/);
    expect(testHostsLayoutSource).not.toMatch(/<ChatSessionProvider\b/);
  });
});
