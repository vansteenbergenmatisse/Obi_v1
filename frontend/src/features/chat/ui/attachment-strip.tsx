/**
 * AttachmentStrip — thumbnail preview row for images staged in the composer, rendered above the
 * textarea so it sits at the bottom of the panel with the input (see
 * `docs/rag/OBI-WIDGET-DESIGN.md` §6). Feature-internal — only `Composer` renders it.
 *
 * Pre-send staging only: these previews live in the composer's local state until `send()`
 * base64-encodes them and hands them to `onSend` (PLAN 7.5) — this component itself never talks
 * to the network. Clicking a thumbnail opens a full-size `ImageLightbox` (PLAN 4.7.8); the same
 * lightbox re-renders a sent image from `message-bubble.tsx` once it's in the thread.
 */
"use client";

import { useState } from "react";
import { ImageLightbox } from "./image-lightbox";

export interface ComposerAttachment {
  id: string;
  file: File;
  previewUrl: string;
}

export interface AttachmentStripProps {
  attachments: ComposerAttachment[];
  onRemove: (id: string) => void;
}

export function AttachmentStrip({ attachments, onRemove }: AttachmentStripProps) {
  const [zoomedId, setZoomedId] = useState<string | null>(null);
  const zoomed = attachments.find((attachment) => attachment.id === zoomedId) ?? null;

  if (attachments.length === 0) return null;

  return (
    <div className="flex gap-1.5 motion-safe:animate-[menu-in_180ms_ease-out]">
      {attachments.map((attachment) => {
        const label = attachment.file.name || "Attached image";
        return (
          <div key={attachment.id} className="relative h-10 w-10 shrink-0">
            <button
              type="button"
              aria-label={`View ${label}`}
              onClick={() => setZoomedId(attachment.id)}
              className="block h-10 w-10 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              {/* eslint-disable-next-line @next/next/no-img-element -- local blob preview, not a static asset */}
              <img
                src={attachment.previewUrl}
                alt={label}
                className="h-10 w-10 rounded-md border border-border object-cover"
              />
            </button>
            <button
              type="button"
              aria-label={`Remove ${label}`}
              onClick={() => onRemove(attachment.id)}
              className="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-text text-[10px] leading-none text-accent-contrast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              ×
            </button>
          </div>
        );
      })}
      {zoomed && (
        <ImageLightbox
          src={zoomed.previewUrl}
          alt={zoomed.file.name || "Attached image"}
          onClose={() => setZoomedId(null)}
        />
      )}
    </div>
  );
}
