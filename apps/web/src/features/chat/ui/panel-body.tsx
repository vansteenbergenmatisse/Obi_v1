/**
 * PanelBody — composition root shared by the full-page `ChatPanel` and the
 * floating `ChatWidget` (PLAN 4.7.3; `ChatWidget` itself lands in 4.7.4).
 * Composes the header, message thread, and composer against the shared
 * `useChatSession()` context. `position: relative` so the header's menus
 * anchor here rather than to the page.
 *
 * The `variant` prop distinguishes layout context only — this component never
 * adds the mockup's docked/floating frame chrome (border, shadow) itself; that
 * is `floating-frame.tsx`'s job for the widget variant (PLAN 4.7.4's own
 * "Panel frame" architecture note). The page variant renders inline, exactly
 * as it did before this sub-step, plus the new header.
 */
"use client";

import { Composer } from "./composer";
import { MessageList } from "./message-list";
import { PanelHeader } from "./panel-header";
import { useChatSession } from "./chat-session-provider";

export interface PanelBodyProps {
  variant: "page" | "widget";
  assistantName?: string;
  onClose?: () => void;
}

export function PanelBody({ variant, assistantName, onClose }: PanelBodyProps) {
  const { messages, pending, sendMessage, handleFeedback, restart } = useChatSession();

  return (
    <section
      className="relative flex w-full flex-col"
      aria-label="Chat"
      data-variant={variant}
    >
      <PanelHeader assistantName={assistantName} onRestart={restart} onClose={onClose} />
      <div className="flex-1 overflow-y-auto px-md pb-[12px] pt-md">
        <div className="flex flex-col gap-md">
          <MessageList messages={messages} onFeedback={handleFeedback} />
        </div>
      </div>
      <div className="flex-none px-md pt-md">
        <Composer onSend={sendMessage} disabled={pending} />
      </div>
    </section>
  );
}
