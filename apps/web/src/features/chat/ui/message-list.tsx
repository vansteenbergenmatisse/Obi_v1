/**
 * MessageList — renders the conversation.
 *
 * Feature-internal (used once, by ChatPanel). Presentation only: it maps the
 * feature's `ChatMessage` view-model onto styled bubbles, citation chips, a
 * streaming indicator, and the per-turn feedback control.
 */
import type { ChatMessage } from "../model/messages";

export interface MessageListProps {
  messages: ChatMessage[];
  onFeedback?: (messageId: string, traceId: string, value: 1 | -1) => void;
}

const FOCUS_RING = "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent";

export function MessageList({ messages, onFeedback }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <p className="text-sm text-text-muted">
        No messages yet. Ask a question to get started.
      </p>
    );
  }

  // Announce only the most recently finished turn — not the raw `<ul>` — so screen readers
  // read one coherent turn on completion instead of re-announcing every streamed token delta.
  const lastFinal = [...messages].reverse().find((m) => m.status !== "streaming");

  return (
    <>
      <ul className="flex flex-col gap-md">
        {messages.map((message) => (
          <li
            key={message.id}
            className={
              message.role === "user" ? "self-end text-right" : "self-start"
            }
          >
            {message.status === "refused" && (
              <p className="mb-xs inline-block rounded-sm border border-border bg-surface-raised px-xs py-xs text-xs font-medium text-text">
                Not found in the docs — routed to a human
              </p>
            )}
            <div
              className={[
                "inline-block max-w-prose rounded-lg px-md py-sm text-sm",
                message.role === "user"
                  ? "bg-accent text-accent-contrast"
                  : "bg-surface-raised text-text",
                message.status === "error" ? "border border-border" : "",
              ].join(" ")}
              aria-busy={message.status === "streaming"}
            >
              {message.status === "streaming" && message.text.length === 0 ? (
                <span className="text-text-muted motion-safe:animate-pulse">Thinking…</span>
              ) : (
                message.text
              )}
            </div>
            {message.citations && message.citations.length > 0 && (
              <ul className="mt-xs flex flex-wrap gap-xs">
                {message.citations.map((citation) =>
                  citation.url ? (
                    <li key={citation.id}>
                      <a
                        href={citation.url}
                        target="_blank"
                        rel="noreferrer"
                        className={`inline-block rounded-sm border border-border bg-surface-raised px-sm py-xs text-xs text-text-muted hover:text-text ${FOCUS_RING}`}
                      >
                        [{citation.id}] {citation.title}
                      </a>
                    </li>
                  ) : (
                    <li key={citation.id}>
                      <span
                        className="inline-block rounded-sm border border-border bg-surface-raised px-sm py-xs text-xs text-text-muted opacity-70"
                        title="Source link unavailable"
                      >
                        [{citation.id}] {citation.title} (source unavailable)
                      </span>
                    </li>
                  ),
                )}
              </ul>
            )}
            {message.role === "assistant" &&
              message.traceId &&
              (message.status === "complete" || message.status === "refused") && (
                <div className="mt-xs flex gap-xs" role="group" aria-label="Rate this answer">
                  <button
                    type="button"
                    aria-pressed={message.feedback === 1}
                    onClick={() => onFeedback?.(message.id, message.traceId!, 1)}
                    className={[
                      "rounded-sm border px-sm py-xs text-xs hover:text-text",
                      FOCUS_RING,
                      message.feedback === 1
                        ? "border-accent bg-surface-raised text-text"
                        : "border-border bg-surface-raised text-text-muted",
                    ].join(" ")}
                  >
                    Helpful
                  </button>
                  <button
                    type="button"
                    aria-pressed={message.feedback === -1}
                    onClick={() => onFeedback?.(message.id, message.traceId!, -1)}
                    className={[
                      "rounded-sm border px-sm py-xs text-xs hover:text-text",
                      FOCUS_RING,
                      message.feedback === -1
                        ? "border-accent bg-surface-raised text-text"
                        : "border-border bg-surface-raised text-text-muted",
                    ].join(" ")}
                  >
                    Not helpful
                  </button>
                </div>
              )}
          </li>
        ))}
      </ul>
      <div aria-live="polite" className="sr-only">
        {lastFinal ? `${lastFinal.role === "user" ? "You" : "Assistant"}: ${lastFinal.text}` : ""}
      </div>
    </>
  );
}
