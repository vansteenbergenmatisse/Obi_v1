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

import { useEffect, useRef, useState } from "react";
import { ChatSessionProvider, FloatingFrame, PanelBody, onUnauthorized, useChatSession } from "@/features/chat";
import { initIframeBridge } from "@/features/embed";

export interface EmbedFrameProps {
  /** Exact host-page origins allowed to drive this frame, computed server-side (`page.tsx`) from
   * the active platform domains — never `"*"`. */
  allowedOrigins: string[];
}

export function EmbedFrame({ allowedOrigins }: EmbedFrameProps) {
  // The bridge lives INSIDE the provider (as `EmbedBridge`) so `obi:clear`/scope-change/401 can
  // reach `useChatSession().restart()` — a logout must abort any in-flight stream and wipe the
  // thread, not just hide the panel on an always-mounted session (LC-1/LC-4).
  return (
    <ChatSessionProvider>
      <EmbedBridge allowedOrigins={allowedOrigins} />
    </ChatSessionProvider>
  );
}

function EmbedBridge({ allowedOrigins }: EmbedFrameProps) {
  const [open, setOpen] = useState(false);
  const { restart } = useChatSession();
  // `restart` is a fresh closure each render; hold it in a ref so the bridge/subscription effects
  // depend only on `allowedOrigins`. Re-running `initIframeBridge` resets the in-memory token to
  // null, so it must NOT re-run on every render.
  const restartRef = useRef(restart);
  restartRef.current = restart;

  useEffect(() => {
    return initIframeBridge({
      allowedOrigins,
      // Host launcher clicked → show the panel.
      onOpen: () => setOpen(true),
      // `obi:clear` (logout/session end): the bridge forgets the token AND the conversation is
      // torn down — restart() aborts any in-flight stream (so a late answer generated under the
      // pre-logout token can never land) and clears messages + conversationId, then the panel
      // closes. A re-open starts a fresh, empty thread (LC-1/LC-4).
      onClear: () => {
        restartRef.current();
        setOpen(false);
      },
      // A silent renewal that changed the company/integration scope resets the open conversation
      // so no prior-scope answer bleeds across (LC-2/LC-3/LC-6).
      onScopeChange: () => restartRef.current(),
    });
  }, [allowedOrigins]);

  // A backend 401 on the answer path (a stale/revoked token) clears stale UI (LC-6). Kept separate
  // from the bridge effect so its own subscription lifecycle is independent.
  useEffect(() => onUnauthorized(() => restartRef.current()), []);

  return open ? (
    // `fill`: obi.js sizes the iframe and draws its rounded corners + shadow, so the panel fills
    // the iframe edge-to-edge — no left gap, no border seam inside the rounded corner.
    <FloatingFrame fill>
      <PanelBody />
    </FloatingFrame>
  ) : null;
}
