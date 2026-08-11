/**
 * MessageList — renders the conversation.
 *
 * Feature-internal (used once, by ChatPanel). Presentation only: it shows the greeting when
 * empty, then delegates each turn's rendering to `MessageBubble` (PLAN 4.7.2).
 */
import { MessageBubble } from "./message-bubble";
import type { ChatMessage } from "../model/messages";

export interface MessageListProps {
  messages: ChatMessage[];
  onFeedback?: (messageId: string, traceId: string, value: 1 | -1) => void;
}

/** Resolved with the user (2026-08-11) — drops the mockup's `{userName}` personalization
 * (no fabricated identity). See PLAN.md Phase 4.7's "Copy decisions summary". */
export function Greeting() {
  return (
    <p className="max-w-[95%] text-sm leading-[1.55] text-text">
      Hi there, how can I help you with <b>Omniboost</b>? The more details you provide, the
      better.
    </p>
  );
}

export function MessageList({ messages, onFeedback }: MessageListProps) {
  if (messages.length === 0) {
    return <Greeting />;
  }

  // Announce only the most recently finished turn — not the raw `<ul>` — so screen readers
  // read one coherent turn on completion instead of re-announcing every streamed token delta.
  const lastFinal = [...messages].reverse().find((m) => m.status !== "streaming");

  return (
    <>
      <ul className="flex flex-col gap-md">
        {messages.map((message) => (
          <li key={message.id}>
            <MessageBubble message={message} onFeedback={onFeedback} />
          </li>
        ))}
      </ul>
      <div aria-live="polite" className="sr-only">
        {lastFinal ? `${lastFinal.role === "user" ? "You" : "Assistant"}: ${lastFinal.text}` : ""}
      </div>
    </>
  );
}
