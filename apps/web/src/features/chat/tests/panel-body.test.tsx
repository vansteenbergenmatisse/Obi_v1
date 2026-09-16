/**
 * PanelBody — characterization test.
 *
 * Replaces the coverage `chat-panel.test.tsx` carried before `ChatPanel` was removed in favor of
 * the widget-only `PanelBody` composition (PLAN 4.7's "Known gaps / debt": that deletion left
 * streaming, citations, refusal, error, feedback, restart, and abort-on-unmount without a
 * replacement). Same scenarios, same assertions, adapted to `PanelBody`'s real rendered structure
 * (composer send button, message bubbles, panel-header's "More" menu) rather than `ChatPanel`'s.
 * Deliberately does not assert on empty-state copy or bubble/feedback-control markup beyond what
 * each scenario needs — those are covered by `message-list.test.tsx`/`message-bubble.test.tsx`.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ChatStreamEvent } from "@omniboost/contracts";

// panel w-screenshot: `handleScreenshot` dynamically imports `html-to-image`'s `toBlob` — mock
// the module itself (works for a dynamic `import()` the same way it does for a static one) rather
// than the composer ref, since this file already renders the real `Composer` via `PanelBody`.
const { toBlobMock } = vi.hoisted(() => ({
  toBlobMock: vi.fn(),
}));
vi.mock("html-to-image", () => ({
  toBlob: toBlobMock,
}));

import { ChatSessionProvider } from "../ui/chat-session-provider";
import { PanelBody } from "../ui/panel-body";

function renderPanel() {
  return render(
    <ChatSessionProvider>
      <PanelBody onClose={vi.fn()} />
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
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
}

describe("PanelBody", () => {
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

describe("handleScreenshot (panel w-screenshot)", () => {
  // The real `data-obi-widget-root` marker lives on `floating-frame.tsx`, which this file's
  // `renderPanel()` doesn't render — add the same wrapper here so `document.querySelector`
  // finds it, same as it would in the real widget tree.
  function renderWithWidgetRoot() {
    render(
      <div data-obi-widget-root="">
        <ChatSessionProvider>
          <PanelBody onClose={vi.fn()} />
        </ChatSessionProvider>
      </div>,
    );
    return document.querySelector<HTMLElement>("[data-obi-widget-root]")!;
  }

  async function clickScreenshotButton() {
    await userEvent.click(screen.getByRole("button", { name: /screenshot/i }));
  }

  beforeEach(() => {
    toBlobMock.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("hides the widget root during capture and restores it after a successful capture", async () => {
    let visibilityDuringCapture: string | undefined;
    toBlobMock.mockImplementation(async () => {
      const widgetRoot = document.querySelector<HTMLElement>("[data-obi-widget-root]");
      visibilityDuringCapture = widgetRoot?.style.visibility;
      return new Blob(["fake-bytes"], { type: "image/png" });
    });

    const widgetRoot = renderWithWidgetRoot();
    expect(widgetRoot.style.visibility).toBe("");

    await clickScreenshotButton();

    await waitFor(() => expect(visibilityDuringCapture).toBe("hidden"));
    await waitFor(() => expect(widgetRoot.style.visibility).toBe(""));
  });

  it("restores the widget root's visibility even when the capture fails", async () => {
    toBlobMock.mockRejectedValue(new Error("capture failed"));

    const widgetRoot = renderWithWidgetRoot();

    await clickScreenshotButton();

    await waitFor(() => expect(toBlobMock).toHaveBeenCalled());
    await waitFor(() => expect(widgetRoot.style.visibility).toBe(""));
  });

  it("calls html-to-image's toBlob with document.body and a white background", async () => {
    toBlobMock.mockResolvedValue(new Blob(["fake-bytes"], { type: "image/png" }));

    renderWithWidgetRoot();
    await clickScreenshotButton();

    await waitFor(() =>
      expect(toBlobMock).toHaveBeenCalledWith(document.body, { backgroundColor: "#ffffff" }),
    );
  });

  it("wraps the captured blob into a PNG file and lands it in the attachment strip", async () => {
    toBlobMock.mockResolvedValue(new Blob(["fake-bytes"], { type: "image/png" }));

    renderWithWidgetRoot();
    await clickScreenshotButton();

    // The composer's attachment strip renders each attachment's `File.name` as alt text (same
    // assertion style `composer.test.tsx` uses for file-picker/paste attachments) — its presence
    // here proves the wrapped `File` reached `composerRef.current.addAttachmentFile(...)`.
    const thumbnail = await screen.findByAltText(/^Screenshot .*\.png$/);
    expect(thumbnail).toBeInTheDocument();
  });
});
