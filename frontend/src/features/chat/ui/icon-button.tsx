/**
 * IconButton — small icon-only button used throughout the widget's chrome
 * (panel header actions, dropdown-menu triggers, composer actions).
 *
 * Feature-internal for now — every consumer lives inside `features/chat/ui`.
 * Promote to `components/ui/` the day a second feature needs an icon button.
 */
import { forwardRef } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Visually distinct "on" state, e.g. a dropdown trigger while its menu is open. */
  active?: boolean;
  children: ReactNode;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  function IconButton({ active = false, className = "", type, children, ...props }, ref) {
    return (
      <button
        ref={ref}
        type={type ?? "button"}
        aria-pressed={active}
        className={[
          "inline-flex items-center justify-center rounded-md",
          "text-text-muted transition-colors duration-fast",
          "hover:bg-surface-sunken hover:text-text",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
          "disabled:cursor-not-allowed disabled:opacity-50",
          active ? "bg-surface-sunken text-text" : "",
          className,
        ].join(" ")}
        {...props}
      >
        {children}
      </button>
    );
  },
);
