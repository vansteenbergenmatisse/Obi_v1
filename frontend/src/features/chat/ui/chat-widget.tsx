/**
 * ChatWidget — the floating chat widget's public root (PLAN 4.7.4): launcher → teaser → panel.
 *
 * Mounted once, globally, in `frontend/src/app/layout.tsx` alongside `ChatSessionProvider`
 * (architecture decision D0) so it reads the exact same live conversation as the full-page
 * `ChatPanel` — never a second, independent session. Timing/animation values come from
 * `useWidgetVisibility` and the design spec in `docs/rag/PLAN.md` Phase 4.7.
 */
"use client";

import { ChatLauncher } from "./chat-launcher";
import { FloatingFrame } from "./floating-frame";
import { PanelBody } from "./panel-body";
import { TeaserPopup } from "./teaser-popup";
import { useWidgetVisibility } from "./use-widget-visibility";

export interface ChatWidgetProps {
  /** "Obi" is the mockup's placeholder name, not a confirmed product decision. */
  assistantName?: string;
}

export function ChatWidget({ assistantName }: ChatWidgetProps) {
  const { open, teaser, openWidget, closeWidget, dismissTeaser } = useWidgetVisibility();

  if (open) {
    return (
      <FloatingFrame>
        <PanelBody assistantName={assistantName} onClose={closeWidget} />
      </FloatingFrame>
    );
  }

  return (
    <>
      {teaser ? <TeaserPopup onOpen={openWidget} onDismiss={dismissTeaser} /> : null}
      <ChatLauncher onOpen={openWidget} pulsing={teaser} />
    </>
  );
}
