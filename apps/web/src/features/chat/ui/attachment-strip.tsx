/**
 * AttachmentStrip — thumbnail preview row for images attached to the composer, rendered above
 * the textarea so it sits at the bottom of the panel with the input (see
 * `docs/rag/OBI-WIDGET-DESIGN.md` §6). Feature-internal — only `Composer` renders it.
 *
 * Client-side preview only: no upload endpoint exists yet, so these previews never leave the
 * browser (see the Composer's send-time notice). Clicking a thumbnail opens a full-size
 * `ImageLightbox` (PLAN 4.7.8) — that's local preview only, not analysis; sending the image to a
 * vision-capable backend call is separate, tracked as PLAN.md Phase 7.
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
