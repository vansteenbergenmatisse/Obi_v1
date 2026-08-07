/**
 * MessageList — renders the conversation.
 *
 * Feature-internal (used once, by ChatPanel). Presentation only: it maps the
 * feature's `ChatMessage` view-model onto styled bubbles and citation chips.
 */
import type { ChatMessage } from "../model/messages";

export interface MessageListProps {
  messages: ChatMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <p className="text-sm text-text-muted">
        No messages yet. Ask a question to get started.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-md" aria-live="polite">
      {messages.map((message) => (
        <li
          key={message.id}
          className={
            message.role === "user" ? "self-end text-right" : "self-start"
          }
        >
          <div
            className={[
              "inline-block max-w-prose rounded-lg px-md py-sm text-sm",
              message.role === "user"
                ? "bg-accent text-accent-contrast"
                : "bg-surface-raised text-text",
              message.status === "error" ? "border border-border" : "",
            ].join(" ")}
          >
            {message.text}
          </div>
          {message.citations && message.citations.length > 0 && (
            <ul className="mt-xs flex flex-wrap gap-xs">
              {message.citations.map((citation) => (
                <li key={citation.id}>
                  <a
                    href={citation.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-block rounded-sm border border-border px-sm py-xs text-xs text-text-muted hover:text-text"
                  >
                    {citation.title}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}
