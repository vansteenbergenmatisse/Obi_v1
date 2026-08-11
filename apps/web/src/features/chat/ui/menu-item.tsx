/**
 * MenuItem — shared row for both the "···" menu and the language menu (PLAN 4.7.3).
 *
 * Disabled items use `aria-disabled`, not the native `disabled` attribute — a real
 * `disabled` button drops out of the tab order entirely, which is worse for a menu
 * item that should still be reachable and announced as unavailable (docs/support
 * stubs, per the Phase 4.7 design spec).
 */
"use client";

import type { ReactNode } from "react";

export interface MenuItemProps {
  onSelect?: () => void;
  disabled?: boolean;
  danger?: boolean;
  /** Bold weight for the currently-selected language item. */
  active?: boolean;
  trailing?: ReactNode;
  children: ReactNode;
}

export function MenuItem({
  onSelect,
  disabled = false,
  danger = false,
  active = false,
  trailing,
  children,
}: MenuItemProps) {
  return (
    <button
      type="button"
      role="menuitem"
      aria-disabled={disabled || undefined}
      title={disabled ? "Coming soon" : undefined}
      onClick={disabled ? undefined : onSelect}
      className={[
        "flex w-full items-center justify-between gap-4 px-4 py-2.5 text-left text-[13.5px] transition-colors duration-fast",
        active ? "font-semibold" : "font-normal",
        disabled
          ? "cursor-not-allowed text-text-muted"
          : danger
            ? "text-danger hover:bg-danger-bg"
            : "text-text hover:bg-surface-sunken",
      ].join(" ")}
    >
      <span>{children}</span>
      {trailing}
    </button>
  );
}
