/**
 * ChatPanel — characterization test.
 *
 * Written before the Phase 4.7.2 `ChatSessionProvider` extraction (PLAN 4.7.2) to lock in
 * ChatPanel's existing conversation behavior — streaming, citations, refusal, error, feedback,
 * and abort-on-unmount — so the refactor into a context provider (and the later visual rebuild
 * of the message/composer markup) can't silently change what the feature *does*. Deliberately
 * does not assert on the empty-state copy or on bubble/feedback-control markup — those are
 * expected to change within this same sub-step (resolved greeting copy, icon-only feedback
 * buttons) and are covered by their own component tests instead.
 *
 * PLAN 4.7.4 (D0) lifted `ChatSessionProvider`'s mount out of `ChatPanel` and into
 * `app/layout.tsx`, so this test now provides it explicitly via `renderPanel` below — matching
 * how the real app renders `ChatPanel` inside the ambient provider today.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ChatStreamEvent } from "@omniboost/contracts";
import { ChatSessionProvider } from "../ui/chat-session-provider";
import { ChatPanel } from "../ui/chat-panel";

function renderPanel() {
  return render(
    <ChatSessionProvider>
      <ChatPanel />
    </ChatSessionProvider>,
  );
}

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

async function sendMessage(text: string) {
  const box = screen.getByRole("textbox", { name: /message/i });
  await userEvent.type(box, text);
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
}

describe("ChatPanel", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("streams an answer and renders the final text", async () => {
    fetchMock.mockResolvedValue(
      okStreamResponse([
        sse({ type: "start", conversationId: "conv-1" }),
        sse({ type: "token", delta: "Hello" }),
        sse({ type: "token", delta: " there" }),
        sse({ type: "done", answer: "Hello there", citations: [], traceId: "trace-1", refused: false }),
      ]),
    );

    renderPanel();
    await sendMessage("hi");

    expect(await screen.findByText("hi")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Hello there")).toBeInTheDocument());
  });

  it("renders citation links returned with the done event", async () => {
    fetchMock.mockResolvedValue(
      okStreamResponse([
        sse({ type: "start", conversationId: "conv-1" }),
        sse({
          type: "done",
          answer: "See the docs",
          citations: [{ id: "1", pageId: "p1", title: "Runbook", url: "https://example.com/p1" }],
          traceId: "trace-1",
          refused: false,
        }),
      ]),
    );

    renderPanel();
    await sendMessage("where are the docs");

    const link = await screen.findByRole("link", { name: /Runbook/ });
    expect(link).toHaveAttribute("href", "https://example.com/p1");
  });

  it("shows a refusal indicator when the pipeline refuses", async () => {
    fetchMock.mockResolvedValue(
      okStreamResponse([
        sse({ type: "start", conversationId: "conv-1" }),
        sse({ type: "done", answer: "I don't know", citations: [], traceId: "trace-1", refused: true }),
      ]),
    );

    renderPanel();
    await sendMessage("something obscure");

    expect(await screen.findByText(/routed to a human/i)).toBeInTheDocument();
  });

  it("surfaces a request error without crashing", async () => {
    fetchMock.mockRejectedValue(new TypeError("network down"));

    renderPanel();
    await sendMessage("hi");

    expect(await screen.findByText("network down")).toBeInTheDocument();
  });

  it("sends feedback for the correct trace id and value", async () => {
    fetchMock.mockImplementation((url: string) => {
      if (typeof url === "string" && url.includes("/feedback")) {
        return Promise.resolve(new Response(JSON.stringify({ ok: true }), { status: 200 }));
      }
      return Promise.resolve(
        okStreamResponse([
          sse({ type: "start", conversationId: "conv-1" }),
          sse({ type: "done", answer: "answer text", citations: [], traceId: "trace-1", refused: false }),
        ]),
      );
    });

    renderPanel();
    await sendMessage("hi");
    await screen.findByText("answer text");

    await userEvent.click(screen.getByRole("button", { name: "Helpful" }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/trace-1/feedback"),
        expect.objectContaining({ body: JSON.stringify({ feedback: 1 }) }),
      ),
    );
  });

  it("restart (via the header's More menu) genuinely clears the thread", async () => {
    fetchMock.mockResolvedValue(
      okStreamResponse([
        sse({ type: "start", conversationId: "conv-1" }),
        sse({ type: "done", answer: "answer text", citations: [], traceId: "trace-1", refused: false }),
      ]),
    );

    renderPanel();
    await sendMessage("hi");
    await screen.findByText("answer text");

    await userEvent.click(screen.getByRole("button", { name: "More" }));
    await userEvent.click(screen.getByRole("menuitem", { name: "Restart conversation" }));

    expect(screen.queryByText("hi")).not.toBeInTheDocument();
    expect(screen.queryByText("answer text")).not.toBeInTheDocument();
    expect(await screen.findByText(/Hi there, how can I help you with/)).toBeInTheDocument();
  });

  it("aborts the in-flight stream when unmounted", async () => {
    let capturedSignal: AbortSignal | undefined;
    fetchMock.mockImplementation((_url: string, init?: RequestInit) => {
      capturedSignal = init?.signal ?? undefined;
      return new Promise(() => {
        /* never resolves — simulates an in-flight request at unmount time */
      });
    });

    const { unmount } = renderPanel();
    await sendMessage("hi");

    await waitFor(() => expect(capturedSignal).toBeDefined());
    expect(capturedSignal?.aborted).toBe(false);

    unmount();

    expect(capturedSignal?.aborted).toBe(true);
  });
});
