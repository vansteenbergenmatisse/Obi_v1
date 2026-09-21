import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MessageBubble } from "../ui/message-bubble";
import { ChatSessionProvider } from "../ui/chat-session-provider";
import type { ChatMessage } from "../model/messages";

afterEach(() => cleanup());

function userMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return { id: "u1", role: "user", text: "hello", status: "complete", ...overrides };
}

function assistantMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return { id: "a1", role: "assistant", text: "answer", status: "complete", ...overrides };
}

describe("MessageBubble", () => {
  it("renders a user message in a filled, right-aligned bubble", () => {
    render(<MessageBubble message={userMessage()} />);
    const bubble = screen.getByText("hello");
    expect(bubble).toHaveClass("bg-surface-sunken");
  });

  it("renders an assistant message as plain text with no bubble fill", () => {
    render(<MessageBubble message={assistantMessage()} />);
    const text = screen.getByText("answer");
    expect(text).not.toHaveClass("bg-surface-sunken");
    expect(text.className).not.toMatch(/bg-accent\b/);
  });

  it("shows the typing indicator instead of text while streaming with nothing received yet", () => {
    render(<MessageBubble message={assistantMessage({ text: "", status: "streaming" })} />);
    expect(screen.getByTestId("typing-word")).toBeInTheDocument();
  });

  // panel w-render · substep p0-s0_5-reg-the-widget
  // "Tokens: appended as they stream" — as the streaming turn's text grows (each token appended
  // by the session provider), the bubble shows the full accumulated text, not just the newest
  // delta, and drops the typing indicator once the first token has arrived.
  it("w_render_appends_streamed_tokens_as_they_arrive", () => {
    const { rerender } = render(
      <MessageBubble message={assistantMessage({ text: "Hel", status: "streaming" })} />,
    );
    expect(screen.getByText("Hel")).toBeInTheDocument();
    expect(screen.queryByTestId("typing-word")).not.toBeInTheDocument();

    rerender(<MessageBubble message={assistantMessage({ text: "Hello", status: "streaming" })} />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.queryByText("Hel")).not.toBeInTheDocument();
  });

  describe("refusal + human hand-off (PLAN 9.6, ADR-0008 decision 6)", () => {
    it("shows the refusal banner and a mailto hand-off CTA for a refused turn", () => {
      render(
        <ChatSessionProvider>
          <MessageBubble message={assistantMessage({ status: "refused" })} />
        </ChatSessionProvider>,
      );
      expect(screen.getByText(/routed to a human/i)).toBeInTheDocument();
      const handoffLink = screen.getByRole("link", { name: "test@gmail.com" });
      expect(handoffLink).toHaveAttribute("href", "mailto:test@gmail.com");
    });

    it("renders no hand-off CTA on a non-refused turn", () => {
      render(<MessageBubble message={assistantMessage({ status: "complete" })} />);
      expect(screen.queryByRole("link", { name: "test@gmail.com" })).not.toBeInTheDocument();
    });

    it("keeps the banner + CTA for a hand-off refusal reason (weak_score)", () => {
      render(
        <ChatSessionProvider>
          <MessageBubble message={assistantMessage({ status: "refused", refusalReason: "weak_score" })} />
        </ChatSessionProvider>,
      );
      expect(screen.getByText(/routed to a human/i)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "test@gmail.com" })).toBeInTheDocument();
    });

    // panel w-render · substep p0-s0_5-reg-the-widget
    // "Refusal: red banner, hand-off email link, feedback thumbs" — all three must appear
    // together on a refused turn that carries a traceId (the standalone refusal tests above
    // never pass a traceId, so they never exercise the feedback thumbs half of this bullet).
    it("w_render_refusal_shows_red_banner_handoff_link_and_feedback_thumbs", () => {
      render(
        <ChatSessionProvider>
          <MessageBubble message={assistantMessage({ status: "refused", traceId: "trace-1" })} />
        </ChatSessionProvider>,
      );

      const banner = screen.getByText(/routed to a human/i);
      expect(banner.className).toMatch(/text-danger\b/);
      expect(banner.className).toMatch(/bg-danger-bg\b/);

      const handoffLink = screen.getByRole("link", { name: "test@gmail.com" });
      expect(handoffLink).toHaveAttribute("href", "mailto:test@gmail.com");

      expect(screen.getByRole("button", { name: "Helpful" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Not helpful" })).toBeInTheDocument();
    });

    it("shows NO banner and NO hand-off CTA for an off_topic redirect — just the softer body", () => {
      render(
        <ChatSessionProvider>
          <MessageBubble
            message={assistantMessage({
              status: "refused",
              refusalReason: "off_topic",
              text: "I can only answer questions about your documentation.",
            })}
          />
        </ChatSessionProvider>,
      );
      expect(screen.queryByText(/routed to a human/i)).not.toBeInTheDocument();
      expect(screen.queryByRole("link", { name: "test@gmail.com" })).not.toBeInTheDocument();
      expect(
        screen.getByText(/only answer questions about your documentation/i),
      ).toBeInTheDocument();
    });
  });

  describe("clarification turns (PLAN 9.3/9.5)", () => {
    afterEach(() => vi.unstubAllGlobals());

    it("shows a distinct clarifying banner, not the refusal banner", () => {
      render(
        <ChatSessionProvider>
          <MessageBubble message={assistantMessage({ status: "clarifying", text: "Which kind of limit?" })} />
        </ChatSessionProvider>,
      );
      expect(screen.getByText(/one more detail/i)).toBeInTheDocument();
      expect(screen.queryByText(/routed to a human/i)).not.toBeInTheDocument();
    });

    it("renders a quick-reply chip per clarification option and sends it on click", async () => {
      let requestBody: unknown;
      const fetchMock = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
        requestBody = init?.body ? JSON.parse(init.body as string) : undefined;
        return Promise.resolve(
          new Response(new ReadableStream({ start: (c) => c.close() }), {
            status: 200,
            headers: { "content-type": "text/event-stream" },
          }),
        );
      });
      vi.stubGlobal("fetch", fetchMock);

      render(
        <ChatSessionProvider>
          <MessageBubble
            message={assistantMessage({
              status: "clarifying",
              text: "Which kind of limit?",
              clarificationOptions: ["Expense limits", "Approval thresholds"],
            })}
          />
        </ChatSessionProvider>,
      );

      expect(screen.getByRole("button", { name: "Expense limits" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Approval thresholds" })).toBeInTheDocument();

      await userEvent.click(screen.getByRole("button", { name: "Expense limits" }));
      await waitFor(() => expect(fetchMock).toHaveBeenCalled());
      expect((requestBody as { history: Array<{ content: string }> }).history.at(-1)?.content).toBe(
        "Expense limits",
      );
    });

    it("renders no chips when the turn has no clarification options", () => {
      render(
        <ChatSessionProvider>
          <MessageBubble message={assistantMessage({ status: "clarifying", text: "Which kind of limit?" })} />
        </ChatSessionProvider>,
      );
      expect(screen.queryByRole("button")).not.toBeInTheDocument();
    });

    it("never shows feedback controls on a clarifying turn (no trace row is written)", () => {
      render(
        <ChatSessionProvider>
          <MessageBubble message={assistantMessage({ status: "clarifying", text: "Which kind of limit?" })} />
        </ChatSessionProvider>,
      );
      expect(screen.queryByRole("button", { name: "Helpful" })).not.toBeInTheDocument();
    });
  });

  it("renders citation links when a url is present", () => {
    render(
      <MessageBubble
        message={assistantMessage({
          citations: [{ id: "1", pageId: "p1", title: "Runbook", url: "https://example.com/p1" }],
        })}
      />,
    );
    expect(screen.getByRole("link", { name: /Runbook/ })).toHaveAttribute("href", "https://example.com/p1");
  });

  it("renders an unavailable-source badge when a citation has no url", () => {
    render(
      <MessageBubble
        message={assistantMessage({
          citations: [{ id: "1", pageId: "p1", title: "Runbook", url: "" }],
        })}
      />,
    );
    expect(screen.getByText(/source unavailable/i)).toBeInTheDocument();
  });

  // panel w-render · substep p0-s0_5-reg-the-widget
  // "Citations: chips with a link; no URL renders as a span marked unavailable" — a citation
  // without a url must render as a non-interactive <span> carrying an "unavailable" mark, never
  // as a clickable link.
  it("w_render_citation_without_url_renders_unavailable_span", () => {
    render(
      <MessageBubble
        message={assistantMessage({
          citations: [{ id: "1", pageId: "p1", title: "Runbook", url: "" }],
        })}
      />,
    );
    const badge = screen.getByTitle("Source link unavailable");
    expect(badge.tagName).toBe("SPAN");
    expect(badge).toHaveTextContent(/source unavailable/i);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("shows thumbs feedback controls for a complete turn with a traceId", async () => {
    const onFeedback = vi.fn();
    render(
      <MessageBubble message={assistantMessage({ traceId: "trace-1" })} onFeedback={onFeedback} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Helpful" }));
    expect(onFeedback).toHaveBeenCalledWith("a1", "trace-1", 1);

    await userEvent.click(screen.getByRole("button", { name: "Not helpful" }));
    expect(onFeedback).toHaveBeenCalledWith("a1", "trace-1", -1);
  });

  it("reflects a previously-submitted rating", () => {
    render(<MessageBubble message={assistantMessage({ traceId: "trace-1", feedback: 1 })} />);
    expect(screen.getByRole("button", { name: "Helpful" })).toHaveAttribute("aria-pressed", "true");
  });

  it("hides feedback controls while streaming (no traceId yet)", () => {
    render(<MessageBubble message={assistantMessage({ status: "streaming" })} />);
    expect(screen.queryByRole("button", { name: "Helpful" })).not.toBeInTheDocument();
  });

  it("never shows feedback controls for the user's own messages", () => {
    render(<MessageBubble message={userMessage()} />);
    expect(screen.queryByRole("button", { name: "Helpful" })).not.toBeInTheDocument();
  });

  describe("image attachments (PLAN 7.5)", () => {
    it("renders a user turn's attached images and opens a lightbox on click", async () => {
      render(
        <MessageBubble
          message={userMessage({
            text: "what is this?",
            images: [{ id: "u1-image-0", previewUrl: "blob:mock-url", alt: "screenshot.png" }],
          })}
        />,
      );

      const thumbnail = screen.getByAltText("screenshot.png");
      expect(thumbnail).toBeInTheDocument();

      await userEvent.click(screen.getByRole("button", { name: "View screenshot.png" }));
      expect(screen.getByRole("dialog", { name: "screenshot.png" })).toBeInTheDocument();
    });

    it("does not render an empty bubble for an image-only turn with no text", () => {
      render(
        <MessageBubble
          message={userMessage({
            text: "",
            images: [{ id: "u1-image-0", previewUrl: "blob:mock-url", alt: "screenshot.png" }],
          })}
        />,
      );

      expect(screen.getByAltText("screenshot.png")).toBeInTheDocument();
      expect(document.querySelector(".bg-surface-sunken")).not.toBeInTheDocument();
    });

    it("renders a labeled vision-analysis block for an assistant turn that has one", () => {
      render(
        <ChatSessionProvider>
          <MessageBubble
            message={assistantMessage({
              imageAnalysis: "The screenshot shows a dashboard with three charts.",
            })}
          />
        </ChatSessionProvider>,
      );

      expect(screen.getByText("Obi looked at your image")).toBeInTheDocument();
      expect(
        screen.getByText("The screenshot shows a dashboard with three charts."),
      ).toBeInTheDocument();
    });

    it("renders no vision-analysis block when the turn has none", () => {
      render(<MessageBubble message={assistantMessage()} />);
      expect(screen.queryByText("Obi looked at your image")).not.toBeInTheDocument();
    });
  });
});
