/**
 * Client half of the `/embed` frame — route-owned, single consumer (`page.tsx`), so it stays here
 * rather than in `features/embed` (which is the postMessage bridge + CSP reader, not UI).
 * Wires `initIframeBridge` for the life of the frame and renders the existing chat PANEL with NO
 * `knowledgeScope` prop: scope is derived server-side from the verified `X-Obi-Token` the browser
 * now forwards on every `POST /api/chat` (PLAN 11.1c, ADR-0014).
 *
 * Unlike the main site, the embed does NOT mount the full `ChatWidget` (launcher + teaser +
 * panel): the host page's `obi.js` injects the one launcher (the "star") and shows/hides this
 * whole iframe, so a second, nested launcher inside the frame would be wrong. Instead the frame
 * renders the panel directly, opened by the `obi:open` message the launcher sends on click. The
 * launcher is the single open/close control, so the panel shows no Close chrome here.
 */
"use client";

import { useEffect, useState } from "react";
import { ChatSessionProvider, FloatingFrame, PanelBody } from "@/features/chat";
import { initIframeBridge } from "@/features/embed";

export interface EmbedFrameProps {
  /** Exact host-page origins allowed to drive this frame, computed server-side (`page.tsx`) from
   * the active platform domains — never `"*"`. */
  allowedOrigins: string[];
}

export function EmbedFrame({ allowedOrigins }: EmbedFrameProps) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    return initIframeBridge({
      allowedOrigins,
      // Host launcher clicked → show the panel. `obi:clear` (logout/session end) closes it and the
      // bridge forgets the token.
      onOpen: () => setOpen(true),
      onClear: () => setOpen(false),
    });
  }, [allowedOrigins]);

  return (
    <ChatSessionProvider>
      {open ? (
        <FloatingFrame>
          <PanelBody />
        </FloatingFrame>
      ) : null}
    </ChatSessionProvider>
  );
}
