/**
 * TeaserPopup — the proactive nudge shown above the launcher (PLAN 4.7.4, pixel-exact reference
 * in `docs/rag/PLAN.md` Phase 4.7's design spec, "Teaser popup").
 *
 * Feature-internal, used once by `chat-widget.tsx`. Clicking the card opens the panel, same as
 * clicking the launcher; the dismiss (×) button stops propagation so dismissing never also
 * opens the panel. Copy is the mockup's own generic boilerplate, reused verbatim per the design
 * spec's "Copy decisions summary" (low-stakes, no fabricated identity or product feature).
 */
"use client";

import { AssistantMark } from "./assistant-mark";
import { useChatSession } from "./chat-session-provider";
import { getCopy } from "../model/i18n";

export interface TeaserPopupProps {
  onOpen: () => void;
  onDismiss: () => void;
}

export function TeaserPopup({ onOpen, onDismiss }: TeaserPopupProps) {
  const { locale } = useChatSession();
  const copy = getCopy(locale);
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
      className={[
        "fixed bottom-[92px] right-lg z-widget-menu max-w-[290px] cursor-pointer rounded-2xl",
        "border border-border bg-surface-raised p-[14px_16px] shadow-lg",
        "motion-safe:animate-[teaser-in_300ms_cubic-bezier(0.2,0.9,0.3,1.2)]",
      ].join(" ")}
    >
      <div className="flex items-start gap-[10px]">
        <AssistantMark size={20} className="mt-[1px] flex-none" />
        <p className="text-[13px] leading-[1.5] text-text">{copy.teaser}</p>
        <button
          type="button"
          title="Dismiss"
          aria-label="Dismiss"
          onClick={(event) => {
            event.stopPropagation();
            onDismiss();
          }}
          className="-mr-[6px] -mt-[4px] flex flex-none items-center justify-center border-none bg-transparent p-[2px] text-text-muted transition-colors duration-fast hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>
    </div>
  );
}
