/**
 * Dev-only visual backdrop so the floating widget previews in context, not on a blank page.
 * Safe to delete — no behavior, no data, not part of the product (see
 * `docs/rag/OBI-WIDGET-DESIGN.md` §7). Route-owned, single consumer (`app/page.tsx`) — not a
 * feature, not promoted to `components/`.
 */
import type { ReactNode } from "react";

export interface DevPreviewBackdropProps {
  children?: ReactNode;
}

const SKELETON_ROWS = 3;
const SKELETON_CARDS = 6;

export function DevPreviewBackdrop({ children }: DevPreviewBackdropProps) {
  return (
    <div className="min-h-screen w-full bg-surface">
      <header className="flex h-14 items-center justify-between border-b border-border bg-surface-raised px-xl">
        <div className="h-4 w-28 rounded bg-surface-sunken" />
        <div className="flex items-center gap-md">
          <div className="h-4 w-16 rounded bg-surface-sunken" />
          <div className="h-4 w-16 rounded bg-surface-sunken" />
          <div className="h-8 w-8 rounded-full bg-surface-sunken" />
        </div>
      </header>

      <div className="mx-auto flex max-w-5xl flex-col gap-xl px-xl py-xl">
        {children && (
          <div className="flex flex-col gap-md rounded-lg border border-border bg-surface-raised p-xl">
            {children}
          </div>
        )}

        <div className="flex flex-col gap-sm">
          {Array.from({ length: SKELETON_ROWS }).map((_, index) => (
            <div
              key={index}
              className="h-3 w-full max-w-md rounded bg-surface-sunken"
              aria-hidden="true"
            />
          ))}
        </div>

        <div className="grid grid-cols-1 gap-md sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: SKELETON_CARDS }).map((_, index) => (
            <div
              key={index}
              className="flex h-32 flex-col justify-between rounded-lg border border-border bg-surface-raised p-md"
              aria-hidden="true"
            >
              <div className="h-3 w-1/2 rounded bg-surface-sunken" />
              <div className="h-6 w-1/3 rounded bg-surface-sunken" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
