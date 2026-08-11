/**
 * Menu — shared dropdown shell for the panel header's "···" and language menus
 * (PLAN 4.7.3). Renders an invisible full-viewport overlay that closes the menu
 * on outside click, plus the positioned menu panel itself. Anchors relative to
 * the nearest positioned ancestor (`panel-body.tsx`'s root), not the header —
 * so it escapes the header's own 52px height.
 */
"use client";

import type { ReactNode } from "react";

export interface MenuProps {
  open: boolean;
  onClose: () => void;
  "aria-label": string;
  /** Mockup: 200px for the "···" menu, 190px for the language menu. */
  minWidthClassName?: string;
  children: ReactNode;
}

export function Menu({
  open,
  onClose,
  minWidthClassName = "min-w-[200px]",
  children,
  ...rest
}: MenuProps) {
  if (!open) return null;

  return (
    <>
      {/* Deliberately no z-index utility here: it must stay below the header's own
         `z-widget`, so header icons (e.g. toggling to the other menu) stay clickable
         while this is open — only the two design-token stacking levels exist
         (widget/widget-menu), and giving this the same level as the header would
         let DOM order — not intent — decide which one wins a click. */}
      <div
        data-testid="menu-overlay"
        aria-hidden="true"
        className="fixed inset-0"
        onClick={onClose}
      />
      <div
        role="menu"
        {...rest}
        className={[
          "absolute right-11 top-[46px] z-widget-menu overflow-hidden rounded-lg border border-border bg-surface-raised py-1.5 shadow-md",
          "motion-safe:animate-[menu-in_180ms_ease-out]",
          minWidthClassName,
        ].join(" ")}
      >
        {children}
      </div>
    </>
  );
}
