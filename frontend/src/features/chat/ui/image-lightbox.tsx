/**
 * ImageLightbox — full-size preview overlay for a clicked image thumbnail (PLAN 4.7.8).
 * Frontend-only: it previews whatever image is already in the browser (a staged attachment, a
 * captured screenshot, or — as of PLAN 7.5 — an already-sent image in the thread) and carries no
 * analysis of its content itself; that text comes back separately as `message.imageAnalysis`
 * and renders in its own labeled block (`message-bubble.tsx`'s `ImageAnalysisSection`).
 *
 * Feature-internal; rendered by both `AttachmentStrip` (pre-send) and `MessageBubble` (post-send).
 */
"use client";

import { useEffect } from "react";

export interface ImageLightboxProps {
  src: string;
  alt: string;
  onClose: () => void;
}

export function ImageLightbox({ src, alt, onClose }: ImageLightboxProps) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={alt}
      className="fixed inset-0 z-widget-menu flex items-center justify-center bg-black/70 p-8"
      onClick={onClose}
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- local blob preview, not a static asset */}
      <img
        src={src}
        alt={alt}
        className="max-h-full max-w-full rounded-lg object-contain shadow-lg"
        onClick={(event) => event.stopPropagation()}
      />
      <button
        type="button"
        aria-label="Close preview"
        onClick={onClose}
        className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-full bg-surface-raised text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
      >
        ×
      </button>
    </div>
  );
}
