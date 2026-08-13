import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MessageList, type MessageListProps } from "../ui/message-list";
import { ChatSessionProvider } from "../ui/chat-session-provider";
import type { ChatMessage } from "../model/messages";

afterEach(() => cleanup());

function renderList(props: MessageListProps) {
  return render(
    <ChatSessionProvider>
      <MessageList {...props} />
    </ChatSessionProvider>,
  );
}

describe("MessageList", () => {
  it("shows the resolved greeting with the product name bold, and no suggestion chip", () => {
    renderList({ messages: [] });

    expect(
      screen.getByText(
        (_, node) => node?.tagName === "P" && node.textContent === "Hi there, how can I help you with Omniboost? The more details you provide, the better.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Omniboost").tagName).toBe("B");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders all three empty-state example-query chips and sends the clicked one", async () => {
    const onSuggestion = vi.fn();
    renderList({ messages: [], onSuggestion });

    expect(screen.getByRole("button", { name: "What can you help me with?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "What topics do you know about?" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "How specific should my question be?" }),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "What topics do you know about?" }));
    expect(onSuggestion).toHaveBeenCalledWith("What topics do you know about?");
  });

  it("renders each message via MessageBubble", () => {
    const messages: ChatMessage[] = [
      { id: "u1", role: "user", text: "hi", status: "complete" },
      { id: "a1", role: "assistant", text: "hello back", status: "complete" },
    ];
    render(<MessageList messages={messages} />);

    expect(screen.getByText("hi")).toBeInTheDocument();
    expect(screen.getByText("hello back")).toBeInTheDocument();
  });

  it("forwards feedback clicks to onFeedback with the message id and trace id", async () => {
    const onFeedback = vi.fn();
    const messages: ChatMessage[] = [
      { id: "a1", role: "assistant", text: "hello back", status: "complete", traceId: "trace-1" },
    ];
    render(<MessageList messages={messages} onFeedback={onFeedback} />);

    await userEvent.click(screen.getByRole("button", { name: "Helpful" }));
    expect(onFeedback).toHaveBeenCalledWith("a1", "trace-1", 1);
  });
});
