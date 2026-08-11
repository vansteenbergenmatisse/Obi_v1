/**
 * MessageList — renders the conversation.
 *
 * Feature-internal (used once, by ChatPanel). Presentation only: it shows the greeting when
 * empty, then delegates each turn's rendering to `MessageBubble` (PLAN 4.7.2).
 */
import { MessageBubble } from "./message-bubble";
import { useChatSession } from "./chat-session-provider";
import { getCopy } from "../model/i18n";
import type { ChatMessage } from "../model/messages";

export interface MessageListProps {
  messages: ChatMessage[];
  onFeedback?: (messageId: string, traceId: string, value: 1 | -1) => void;
  /** Sends the empty-state suggestion chip's query through the real chat session. */
  onSuggestion?: (text: string) => void;
}

/** Resolved with the user (2026-08-11) — drops the mockup's `{userName}` personalization
 * (no fabricated identity). See PLAN.md Phase 4.7's "Copy decisions summary". Locale-aware as of
 * 4.7.7 — reads the shared session locale, not a prop, since `MessageList`'s only caller
 * (`panel-body.tsx`) already sits inside `ChatSessionProvider`. */
export function Greeting() {
  const { locale } = useChatSession();
  const copy = getCopy(locale);
  return (
    <p className="max-w-[95%] text-sm leading-[1.55] text-text">
      {copy.greetingPre}
      <b>Omniboost</b>
      {copy.greetingPost}
    </p>
  );
}

/** The mockup's chip literally reads "My verification status" — a Stripe-demo placeholder with
 * no Omniboost/Confluence equivalent, so reusing it verbatim would suggest a feature that doesn't
 * exist. Copy adapted, not dropped: this question is always honestly answerable (it asks the
 * assistant to describe its own scope) and goes through the real session like any typed message. */
function SuggestionChip({ onSelect }: { onSelect: (text: string) => void }) {
  const { locale } = useChatSession();
  const copy = getCopy(locale);
  return (
    <div className="mt-sm flex justify-end">
      <button
        type="button"
        onClick={() => onSelect(copy.suggestion)}
        className={[
          "rounded-full border border-[#8d8bfa] bg-surface-raised px-md py-sm text-sm text-text",
          "transition-all duration-fast hover:-translate-y-px hover:border-accent hover:bg-[#f6f6ff]",
          "hover:shadow-[0_2px_8px_rgba(99,91,255,0.15)]",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
        ].join(" ")}
      >
        {copy.suggestion}
      </button>
    </div>
  );
}

export function MessageList({ messages, onFeedback, onSuggestion }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <>
        <Greeting />
        {onSuggestion ? <SuggestionChip onSelect={onSuggestion} /> : null}
      </>
    );
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
