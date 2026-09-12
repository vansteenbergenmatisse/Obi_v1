/**
 * Client half of the `/embed` frame — route-owned, single consumer (`page.tsx`), so it stays here
 * rather than in `features/embed` (which is the postMessage bridge + CSP reader, not UI).
 * Wires `initIframeBridge` for the life of the frame and renders the existing chat widget with NO
 * `knowledgeScope` prop: scope is derived server-side from the verified `X-Obi-Token` the browser
 * now forwards on every `POST /api/chat` (PLAN 11.1c, ADR-0014).
 */
"use client";

import { useEffect } from "react";
import { ChatSessionProvider, ChatWidget } from "@/features/chat";
import { initIframeBridge } from "@/features/embed";

export interface EmbedFrameProps {
  /** Exact host-page origins allowed to drive this frame, computed server-side (`page.tsx`) from
   * the active platform domains — never `"*"`. */
  allowedOrigins: string[];
}

export function EmbedFrame({ allowedOrigins }: EmbedFrameProps) {
  useEffect(() => {
    return initIframeBridge({ allowedOrigins });
  }, [allowedOrigins]);

  return (
    <ChatSessionProvider>
      <ChatWidget />
    </ChatSessionProvider>
  );
}
