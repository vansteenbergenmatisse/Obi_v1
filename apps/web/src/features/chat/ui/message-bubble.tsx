/**
 * MessageBubble — a single turn in the conversation (PLAN 4.7.2), extracted out of
 * `message-list.tsx`'s inline markup. Feature-internal (used once, by `MessageList`).
 *
 * Only the user's own messages get a filled bubble (`bg-surface-sunken`) — bot turns render as
 * plain text, matching the mockup exactly (`docs/rag/PLAN.md` Phase 4.7's design spec).
 */
import { TypingIndicator } from "./typing-indicator";
import type { ChatMessage } from "../model/messages";

export interface MessageBubbleProps {
  message: ChatMessage;
  onFeedback?: (messageId: string, traceId: string, value: 1 | -1) => void;
}

const FOCUS_RING = "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent";

const THUMB_UP_PATH =
  "M7 10v11H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1h3zm0 0l4-7a2.4 2.4 0 0 1 2.4 2.4V9h5.2a2 2 0 0 1 2 2.4l-1.2 7A2 2 0 0 1 17.4 20H7";

export function MessageBubble({ message, onFeedback }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isPlaceholder = message.status === "streaming" && message.text.length === 0;
  const showFeedback =
    !isUser && message.traceId && (message.status === "complete" || message.status === "refused");

  return (
    <div className={isUser ? "self-end text-right" : "self-start"}>
      {message.status === "refused" && (
        <p className="mb-xs inline-block rounded-sm border border-danger-bg bg-danger-bg px-xs py-xs text-xs font-medium text-danger">
          Not found in the docs — routed to a human
        </p>
      )}

      {isUser ? (
        <div
          className={[
            "inline-block max-w-[82%] rounded-2xl bg-surface-sunken px-[15px] py-[9px] text-sm text-text",
            "motion-safe:animate-[menu-in_180ms_ease-out]",
          ].join(" ")}
        >
          {message.text}
        </div>
      ) : isPlaceholder ? (
        <TypingIndicator />
      ) : (
        <div
          className={[
            "max-w-[96%] whitespace-pre-line text-sm leading-[1.6] text-text",
            message.status === "error" ? "rounded-lg border border-border px-md py-sm" : "",
            "motion-safe:animate-[menu-in_180ms_ease-out]",
          ].join(" ")}
          aria-busy={message.status === "streaming"}
        >
          {message.text}
        </div>
      )}

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

      {showFeedback && (
        <div className="mt-xs flex justify-end gap-1" role="group" aria-label="Rate this answer">
          <button
            type="button"
            aria-label="Helpful"
            aria-pressed={message.feedback === 1}
            onClick={() => onFeedback?.(message.id, message.traceId!, 1)}
            className={[
              "flex h-[26px] w-[26px] items-center justify-center rounded-md transition-colors",
              FOCUS_RING,
              message.feedback === 1 ? "bg-success-bg text-success" : "text-text-muted hover:bg-surface-sunken",
            ].join(" ")}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill={message.feedback === 1 ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8" className={message.feedback === 1 ? "fill-success-fill" : ""}>
              <path d={THUMB_UP_PATH} />
            </svg>
          </button>
          <button
            type="button"
            aria-label="Not helpful"
            aria-pressed={message.feedback === -1}
            onClick={() => onFeedback?.(message.id, message.traceId!, -1)}
            className={[
              "flex h-[26px] w-[26px] items-center justify-center rounded-md transition-colors",
              FOCUS_RING,
              message.feedback === -1 ? "bg-danger-bg text-danger" : "text-text-muted hover:bg-surface-sunken",
            ].join(" ")}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill={message.feedback === -1 ? "currentColor" : "none"}
              stroke="currentColor"
              strokeWidth="1.8"
              style={{ transform: "rotate(180deg)" }}
              className={message.feedback === -1 ? "fill-danger-fill" : ""}
            >
              <path d={THUMB_UP_PATH} />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
