/**
 * PageShell — reusable page layout primitive.
 *
 * A centered, max-width column with consistent padding. Lives in `components/`
 * because more than one route uses it (the home route and the chat route). It
 * carries layout only — no content, no data, no business rules.
 */
import type { ReactNode } from "react";

export interface PageShellProps {
  children: ReactNode;
  /** Vertically center the content (used by the landing hero). */
  center?: boolean;
  className?: string;
}

export function PageShell({
  children,
  center = false,
  className = "",
}: PageShellProps) {
  return (
    <main
      className={[
        "mx-auto flex min-h-screen w-full max-w-3xl flex-col gap-md p-xl",
        center ? "items-center justify-center text-center" : "",
        className,
      ].join(" ")}
    >
      {children}
    </main>
  );
}
