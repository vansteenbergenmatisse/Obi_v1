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
});
