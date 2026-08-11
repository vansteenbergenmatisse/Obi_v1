/**
 * AttachmentStrip — thumbnail preview row for images attached to the composer, rendered above
 * the textarea so it sits at the bottom of the panel with the input (see
 * `docs/rag/OBI-WIDGET-DESIGN.md` §6). Feature-internal — only `Composer` renders it.
 *
 * Client-side preview only: no upload endpoint exists yet, so these previews never leave the
 * browser (see the Composer's send-time notice).
 */

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
  if (attachments.length === 0) return null;

  return (
    <div className="flex gap-1.5 motion-safe:animate-[menu-in_180ms_ease-out]">
      {attachments.map((attachment) => (
        <div key={attachment.id} className="relative h-10 w-10 shrink-0">
          {/* eslint-disable-next-line @next/next/no-img-element -- local blob preview, not a static asset */}
          <img
            src={attachment.previewUrl}
            alt={attachment.file.name || "Attached image"}
            className="h-10 w-10 rounded-md border border-border object-cover"
          />
          <button
            type="button"
            aria-label={`Remove ${attachment.file.name || "attached image"}`}
            onClick={() => onRemove(attachment.id)}
            className="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-text text-[10px] leading-none text-accent-contrast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
