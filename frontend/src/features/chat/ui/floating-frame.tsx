/**
 * FloatingFrame — the widget's open-state panel chrome (PLAN 4.7.4).
 *
 * Architecture difference from the mockup, not a visual one (see PLAN.md Phase 4.7's design
 * spec, "Panel frame"): the mockup lays the panel out as a flex sibling that shrinks its fake
 * host dashboard. This app's real pages aren't designed to share width with a docked panel, so
 * this is a fixed-position overlay pinned to the right edge, full height, sitting on top of page
 * content instead — same visual width/border/shadow as the mockup, different containing
 * mechanism.
 *
 * `fill` (the `/embed` iframe): there, `obi.js` sizes the iframe itself and already draws the
 * rounded corners + shadow (see `features/embed/loader.ts`'s `injectIframe`). Inside that iframe
 * the panel must fill edge-to-edge — the default's right-pinned clamped width would leave a strip
 * of empty iframe on the left and its own `border-l` would draw a seam inside the rounded corner.
 * So `fill` drops the width clamp, the right pin, the left border, and the shadow, and the panel
 * simply fills its iframe.
 */
"use client";

import type { ReactNode } from "react";

export function FloatingFrame({
  children,
  fill = false,
}: {
  children: ReactNode;
  fill?: boolean;
}) {
  return (
    <div
      // Marks the widget's own root so `panel-body.tsx`'s screenshot capture (PLAN 4.7.7) can
      // hide it for one frame — otherwise "screenshot the page behind the widget" would capture
      // the widget itself.
      data-obi-widget-root=""
      className={
        fill
          ? "fixed inset-0 z-widget flex flex-col bg-surface-raised"
          : "fixed inset-y-0 right-0 z-widget flex w-[clamp(360px,29%,440px)] flex-col border-l border-border bg-surface-raised shadow-[-4px_0_16px_rgba(35,38,59,0.04)]"
      }
    >
      {children}
    </div>
  );
}
