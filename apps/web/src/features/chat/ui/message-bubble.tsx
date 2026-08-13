/**
 * MessageBubble — a single turn in the conversation (PLAN 4.7.2), extracted out of
 * `message-list.tsx`'s inline markup. Feature-internal (used once, by `MessageList`).
 *
 * Only the user's own messages get a filled bubble (`bg-surface-sunken`) — bot turns render as
 * plain text, matching the mockup exactly (`docs/rag/PLAN.md` Phase 4.7's design spec).
 */
import { useState } from "react";
import { TypingIndicator } from "./typing-indicator";
import { ImageLightbox } from "./image-lightbox";
import { useChatSession } from "./chat-session-provider";
import { getCopy } from "../model/i18n";
import type { ChatMessage, MessageImage } from "../model/messages";

export interface MessageBubbleProps {
  message: ChatMessage;
  onFeedback?: (messageId: string, traceId: string, value: 1 | -1) => void;
}

const FOCUS_RING = "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent";

const THUMB_UP_PATH =
  "M7 10v11H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1h3zm0 0l4-7a2.4 2.4 0 0 1 2.4 2.4V9h5.2a2 2 0 0 1 2 2.4l-1.2 7A2 2 0 0 1 17.4 20H7";

/** The user turn's attached images (PLAN 7.5) — thumbnails above the bubble, each reusing the
 * 4.7.8 lightbox for a click-to-zoom preview. No copy here, so no `useChatSession` dependency. */
function UserImages({ images }: { images: MessageImage[] }) {
  const [zoomedId, setZoomedId] = useState<string | null>(null);
  const zoomed = images.find((image) => image.id === zoomedId) ?? null;

  return (
    <div className="mb-xs flex justify-end gap-1.5">
      {images.map((image) => (
        <button
          key={image.id}
          type="button"
          aria-label={`View ${image.alt}`}
          onClick={() => setZoomedId(image.id)}
          className={`block h-10 w-10 rounded-md ${FOCUS_RING}`}
        >
          {/* eslint-disable-next-line @next/next/no-img-element -- local blob preview, not a static asset */}
          <img
            src={image.previewUrl}
            alt={image.alt}
            className="h-10 w-10 rounded-md border border-border object-cover"
          />
        </button>
      ))}
      {zoomed && (
        <ImageLightbox src={zoomed.previewUrl} alt={zoomed.alt} onClose={() => setZoomedId(null)} />
      )}
    </div>
  );
}

/** The assistant turn's vision-analysis block (ADR-0009 decision 5) — a separate, labeled
 * section, never merged into `message.text` since it never passes through citation enforcement.
 * Isolated in its own component (same pattern as `Greeting`/`SuggestionChip` in
 * `message-list.tsx`) so `useChatSession` is only required when a turn actually has one. */
function ImageAnalysisSection({ text }: { text: string }) {
  const { locale } = useChatSession();
  const copy = getCopy(locale);
  return (
    <div className="mt-xs max-w-[96%] rounded-lg border border-border bg-surface-raised px-md py-sm">
      <p className="text-xs font-medium text-text-muted">{copy.imageAnalysisLabel}</p>
      <p className="mt-1 whitespace-pre-line text-sm leading-[1.6] text-text">{text}</p>
    </div>
  );
}

/** The "clarifying" status pill (PLAN 9.5, ADR-0008 decision 3) — deliberately styled on the
 * accent tokens, never `danger`, since a clarifying turn is a still-open next step, not a
 * failure like `refused` right above it. */
function ClarifyingBanner() {
  const { locale } = useChatSession();
  const copy = getCopy(locale);
  return (
    <p className="mb-xs inline-block rounded-sm border border-accent-secondary bg-accent-bg px-xs py-xs text-xs font-medium text-accent-hover">
      {copy.clarifyingLabel}
    </p>
  );
}

/** Quick-reply chips for `clarificationOptions` (PLAN 9.3/9.5) — clicking one sends it as the
 * next user message through the same session every typed message goes through. Disabled while
 * another turn is in flight, same guard as the composer. */
function ClarificationChips({ options }: { options: string[] }) {
  const { sendMessage, pending } = useChatSession();
  return (
    <div className="mt-sm flex flex-wrap gap-xs">
      {options.map((option) => (
        <button
          key={option}
          type="button"
          disabled={pending}
          onClick={() => sendMessage(option)}
          className={[
            "rounded-full border border-accent-secondary bg-surface-raised px-md py-sm text-sm text-text",
            "transition-all duration-fast hover:-translate-y-px hover:border-accent hover:bg-accent-bg",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
            "disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0",
          ].join(" ")}
        >
          {option}
        </button>
      ))}
    </div>
  );
}

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

      {message.status === "clarifying" && <ClarifyingBanner />}

      {isUser && message.images && message.images.length > 0 && (
        <UserImages images={message.images} />
      )}

      {isUser ? (
        message.text ? (
          <div
            className={[
              "inline-block max-w-[82%] rounded-2xl bg-surface-sunken px-[15px] py-[9px] text-sm text-text",
              "motion-safe:animate-[menu-in_180ms_ease-out]",
            ].join(" ")}
          >
            {message.text}
          </div>
        ) : null
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

      {!isUser && message.imageAnalysis && <ImageAnalysisSection text={message.imageAnalysis} />}

      {!isUser &&
        message.status === "clarifying" &&
        message.clarificationOptions &&
        message.clarificationOptions.length > 0 && (
          <ClarificationChips options={message.clarificationOptions} />
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
