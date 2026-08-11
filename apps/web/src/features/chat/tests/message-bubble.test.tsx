import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
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

  it("shows the refusal banner for a refused turn", () => {
    render(<MessageBubble message={assistantMessage({ status: "refused" })} />);
    expect(screen.getByText(/routed to a human/i)).toBeInTheDocument();
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
