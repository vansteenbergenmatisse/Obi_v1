/**
 * Composer — chat message input (PLAN 4.7.2, pixel-exact reference in `docs/rag/PLAN.md`
 * Phase 4.7's design spec; image attachment added per `docs/rag/OBI-WIDGET-DESIGN.md` §6, sent for
 * real vision analysis as of PLAN 7.5).
 *
 * Feature-internal (used once, only by ChatPanel).
 *
 * Attachments are base64-encoded here on send (ADR-0009 decision 2: inline on the newest turn
 * only, no upload endpoint) and handed to `onSend` alongside their still-live preview URL, so the
 * caller can both build the wire request and keep rendering the sent image in the thread.
 */
"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import type { ChangeEvent, ClipboardEvent, KeyboardEvent } from "react";
import { IconButton } from "./icon-button";
import { AttachmentStrip, type ComposerAttachment } from "./attachment-strip";
import { useChatSession } from "./chat-session-provider";
import { getCopy } from "../model/i18n";
import type { SentImage } from "../model/messages";

export interface ComposerProps {
  onSend: (message: string, images: SentImage[]) => void;
  disabled?: boolean;
}

/** Imperative escape hatch for `panel-header.tsx`'s screenshot button (PLAN 4.7.7) — the
 * captured image needs to land in this same attachment strip, but attachments are local state
 * here, not lifted, so the header reaches in through a ref instead of a prop round-trip. */
export interface ComposerHandle {
  addAttachmentFile: (file: File) => void;
}

const ATTACH_ICON_PATH =
  "M21 12.5l-8.5 8.5a6 6 0 0 1-8.5-8.5L12.5 4a4 4 0 0 1 5.7 5.7L9.7 18.2a2 2 0 0 1-2.9-2.9l8-8";
const SEND_ICON_PATH = "M12 19V5M6 11l6-6 6 6";

const MAX_ATTACHMENTS = 3;
/** Per-image byte cap, mirroring the backend `chat_max_image_bytes` (decision w-composer-images:
 * ≤ 3 MB, decimal). An image over this is refused here so it never reaches the proxy or the
 * backend's 400 — the backend cap stays as defense in depth. */
const MAX_IMAGE_BYTES = 3_000_000;

/** Reads a `File` as base64 (no data-URI prefix, per `ImageAttachment`'s wire shape) without
 * releasing its still-live `previewUrl` — that URL keeps backing the message-list render. */
function toSentImage(attachment: ComposerAttachment): Promise<SentImage> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      const commaIndex = result.indexOf(",");
      resolve({
        mediaType: attachment.file.type,
        data: commaIndex === -1 ? result : result.slice(commaIndex + 1),
        previewUrl: attachment.previewUrl,
        alt: attachment.file.name || "Attached image",
      });
    };
    reader.onerror = () => reject(reader.error ?? new Error("failed to read attachment"));
    reader.readAsDataURL(attachment.file);
  });
}

export const Composer = forwardRef<ComposerHandle, ComposerProps>(function Composer(
  { onSend, disabled = false },
  ref,
) {
  const { locale } = useChatSession();
  const copy = getCopy(locale);
  const [value, setValue] = useState("");
  const [attachments, setAttachments] = useState<ComposerAttachment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const nextAttachmentId = useRef(0);
  const canSend = (value.trim().length > 0 || attachments.length > 0) && !disabled;

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [value]);

  // Revoke every outstanding preview URL on unmount — nothing else releases them. A sent
  // attachment is removed from this state at send time (ownership moves to the sent message,
  // see `send()`), so this never revokes a URL a message bubble is still rendering.
  useEffect(() => {
    return () => {
      attachments.forEach((attachment) => URL.revokeObjectURL(attachment.previewUrl));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- unmount-only cleanup
  }, []);

  useImperativeHandle(ref, () => ({
    addAttachmentFile: (file: File) => addAttachments([file]),
  }));

  function addAttachments(files: File[]) {
    const images = files.filter((file) => file.type.startsWith("image/"));
    if (images.length === 0) return;

    // Refuse oversized images here so they never reach the proxy/backend (the backend's 400 is
    // defense in depth). An over-limit count is capped and reported, not silently dropped.
    const withinSize = images.filter((file) => file.size <= MAX_IMAGE_BYTES);
    const anyOversized = withinSize.length < images.length;
    const room = Math.max(0, MAX_ATTACHMENTS - attachments.length);
    const accepted = withinSize.slice(0, room);

    if (anyOversized) {
      setError(copy.imageTooLarge);
    } else if (withinSize.length > room) {
      setError(copy.imageTooMany);
    } else {
      setError(null);
    }

    if (accepted.length === 0) return;
    setAttachments((current) => {
      const additions = accepted.map((file) => {
        nextAttachmentId.current += 1;
        return {
          id: `attachment-${nextAttachmentId.current}`,
          file,
          previewUrl: URL.createObjectURL(file),
        };
      });
      return [...current, ...additions];
    });
  }

  function removeAttachment(id: string) {
    setError(null);
    setAttachments((current) => {
      const target = current.find((attachment) => attachment.id === id);
      if (target) URL.revokeObjectURL(target.previewUrl);
      return current.filter((attachment) => attachment.id !== id);
    });
  }

  function clearAttachments() {
    setAttachments((current) => {
      current.forEach((attachment) => URL.revokeObjectURL(attachment.previewUrl));
      return [];
    });
  }

  function handlePaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    const items = event.clipboardData?.items;
    if (!items) return;
    const imageFiles = Array.from(items)
      .filter((item) => item.type.startsWith("image/"))
      .map((item) => item.getAsFile())
      .filter((file): file is File => file !== null);
    if (imageFiles.length === 0) return;
    event.preventDefault();
    addAttachments(imageFiles);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files) addAttachments(Array.from(event.target.files));
    event.target.value = "";
  }

  async function send() {
    if (disabled) return;
    const trimmed = value.trim();
    if (!trimmed && attachments.length === 0) return;

    // Hand off ownership of the staged attachments' preview URLs to the sent message now —
    // `clearAttachments` is not called here, since that would revoke URLs the thread still needs.
    const pendingAttachments = attachments;
    setAttachments([]);
    setValue("");
    setError(null);

    let images: SentImage[] = [];
    try {
      images = await Promise.all(pendingAttachments.map(toSentImage));
    } catch {
      // Fail open: an unreadable attachment never blocks sending the rest of the turn.
    }
    if (!trimmed && images.length === 0) return;
    onSend(trimmed, images);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  }

  return (
    <div className="flex flex-col gap-1">
      <div
        className="flex flex-col gap-1.5 rounded-xl border border-[#8d8bfa] bg-surface-raised p-[12px_12px_8px] shadow-[0_1px_4px_rgba(99,91,255,0.06)]"
      >
        <AttachmentStrip attachments={attachments} onRemove={removeAttachment} />
        <textarea
          ref={textareaRef}
          rows={2}
          aria-label="Message"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          disabled={disabled}
          placeholder={copy.placeholder}
          className="min-h-[42px] resize-none border-none bg-transparent text-sm leading-[1.5] text-text placeholder:text-text-muted focus-visible:outline-none disabled:opacity-50"
        />
        <div className="flex items-center justify-end gap-[10px]">
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            onChange={handleFileChange}
            className="hidden"
            tabIndex={-1}
            aria-hidden="true"
          />
          <IconButton
            aria-label="Attach image"
            title="Attach image"
            disabled={disabled}
            onClick={() => fileInputRef.current?.click()}
            className="h-[28px] w-[28px] rounded-md"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d={ATTACH_ICON_PATH} />
            </svg>
          </IconButton>
          <button
            type="button"
            aria-label="Send"
            title="Send"
            disabled={!canSend}
            onClick={send}
            className={[
              "flex h-[30px] w-[30px] items-center justify-center rounded-full transition-transform duration-fast",
              "hover:enabled:scale-[1.08]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
              "disabled:cursor-not-allowed",
              canSend ? "bg-accent text-accent-contrast" : "bg-surface-sunken text-text-muted",
            ].join(" ")}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d={SEND_ICON_PATH} />
            </svg>
          </button>
        </div>
      </div>
      {error && (
        <p role="alert" className="text-center text-xs text-danger">
          {error}
        </p>
      )}
      {attachments.length > 0 && (
        <p className="text-center text-xs text-text-muted">{copy.imageDisclosure}</p>
      )}
      <p className="text-center text-xs text-text-muted">
        {copy.footer}
      </p>
    </div>
  );
});
