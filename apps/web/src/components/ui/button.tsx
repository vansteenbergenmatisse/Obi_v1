/**
 * Button — reusable UI primitive.
 *
 * Lives in `components/` because it is consumed across more than one place
 * (the home route and the chat feature's composer). It owns no business rules:
 * it maps a `variant` to semantic Tailwind utilities sourced from
 * `@omniboost/design-tokens`, and forwards every native button prop.
 */
import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "ghost";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    "bg-accent text-accent-contrast hover:opacity-90 disabled:opacity-50",
  ghost:
    "bg-transparent text-text border border-border hover:bg-surface-raised disabled:opacity-50",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button({ variant = "primary", className = "", type, ...props }, ref) {
    return (
      <button
        ref={ref}
        type={type ?? "button"}
        className={[
          "inline-flex items-center justify-center gap-sm rounded-md px-md py-sm",
          "text-sm font-medium transition-opacity",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
          "disabled:cursor-not-allowed",
          VARIANT_CLASSES[variant],
          className,
        ].join(" ")}
        {...props}
      />
    );
  },
);
