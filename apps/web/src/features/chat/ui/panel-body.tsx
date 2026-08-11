/**
 * PanelBody — composition root for the floating `ChatWidget` (PLAN 4.7.3/4.7.4). Composes the
 * header, message thread, and composer against the shared `useChatSession()` context.
 * `position: relative` so the header's menus anchor here rather than to the page. Never adds the
 * mockup's docked/floating frame chrome (border, shadow) itself — that is `floating-frame.tsx`'s
 * job (PLAN 4.7.4's "Panel frame" architecture note).
 *
 * Used to also back a full-page `/chat` route in a "page" variant; that route and variant were
 * removed in PLAN 4.7.7 — the widget is now the only chat surface, so this component no longer
 * takes a `variant` prop.
 */
"use client";

import { useRef, useState } from "react";
import { Composer, type ComposerHandle } from "./composer";
import { ContourBackground } from "./contour-background";
import { MessageList } from "./message-list";
import { PanelHeader } from "./panel-header";
import { useChatSession } from "./chat-session-provider";

export interface PanelBodyProps {
  assistantName?: string;
  onClose: () => void;
}

const FLASH_DURATION_MS = 550;

export function PanelBody({ assistantName, onClose }: PanelBodyProps) {
  const { messages, pending, sendMessage, handleFeedback, restart } = useChatSession();
  const composerRef = useRef<ComposerHandle>(null);
  const [flashing, setFlashing] = useState(false);
  const flashTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  async function handleScreenshot() {
    if (typeof document === "undefined") return;

    setFlashing(true);
    if (flashTimeoutRef.current) clearTimeout(flashTimeoutRef.current);
    flashTimeoutRef.current = setTimeout(() => setFlashing(false), FLASH_DURATION_MS);

    // Hide the widget's own root for the capture — otherwise "screenshot the page behind the
    // widget" would just capture the widget.
    const widgetRoot = document.querySelector<HTMLElement>("[data-obi-widget-root]");
    const previousVisibility = widgetRoot?.style.visibility;
    if (widgetRoot) widgetRoot.style.visibility = "hidden";

    try {
      const { toBlob } = await import("html-to-image");
      const blob = await toBlob(document.body, { backgroundColor: "#ffffff" });
      if (blob) {
        const file = new File([blob], `Screenshot ${new Date().toISOString()}.png`, {
          type: "image/png",
        });
        composerRef.current?.addAttachmentFile(file);
      }
    } catch {
      // Best-effort: a failed capture never blocks or disrupts the conversation — same posture
      // as `handleFeedback`'s own best-effort catch above.
    } finally {
      if (widgetRoot) widgetRoot.style.visibility = previousVisibility ?? "";
    }
  }

  return (
    <section className="relative flex h-full w-full flex-col" aria-label="Chat">
      <PanelHeader
        assistantName={assistantName}
        onRestart={restart}
        onClose={onClose}
        onScreenshot={handleScreenshot}
      />
      <div className="relative flex-1 overflow-hidden bg-[#fdfdfe]">
        <ContourBackground />
        <div className="absolute inset-0 overflow-y-auto px-md pb-[12px] pt-md">
          <div className="flex flex-col gap-md">
            <MessageList
              messages={messages}
              onFeedback={handleFeedback}
              onSuggestion={sendMessage}
            />
          </div>
        </div>
        {flashing && (
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 z-widget-menu bg-surface-raised motion-safe:animate-[screenshot-flash_550ms_ease-out_forwards]"
          />
        )}
      </div>
      <div className="flex-none px-md pt-md">
        <Composer ref={composerRef} onSend={sendMessage} disabled={pending} />
      </div>
    </section>
  );
}
