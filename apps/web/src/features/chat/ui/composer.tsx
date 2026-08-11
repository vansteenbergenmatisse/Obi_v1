/**
 * Composer — chat message input (PLAN 4.7.2, pixel-exact reference in `docs/rag/PLAN.md`
 * Phase 4.7's design spec; image attachment added per `docs/rag/OBI-WIDGET-DESIGN.md` §6).
 *
 * Feature-internal (used once, only by ChatPanel).
 *
 * Image attachments are client-side preview only (§6.2, Option A) — no upload endpoint exists,
 * so on send they're dropped with an inline notice rather than silently sent as text.
 */
"use client";

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import type { ChangeEvent, ClipboardEvent, KeyboardEvent } from "react";
import { IconButton } from "./icon-button";
import { AttachmentStrip, type ComposerAttachment } from "./attachment-strip";
import { useChatSession } from "./chat-session-provider";
import { getCopy } from "../model/i18n";

export interface ComposerProps {
  onSend: (message: string) => void;
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

const MAX_ATTACHMENTS = 4;
const ATTACHMENT_NOTICE_MS = 4000;

export const Composer = forwardRef<ComposerHandle, ComposerProps>(function Composer(
  { onSend, disabled = false },
  ref,
) {
  const { locale } = useChatSession();
  const copy = getCopy(locale);
  const [value, setValue] = useState("");
  const [attachments, setAttachments] = useState<ComposerAttachment[]>([]);
  const [showAttachmentNotice, setShowAttachmentNotice] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const noticeTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const nextAttachmentId = useRef(0);
  const canSend = (value.trim().length > 0 || attachments.length > 0) && !disabled;

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, [value]);

  // Revoke every outstanding preview URL on unmount — nothing else releases them.
  useEffect(() => {
    return () => {
      attachments.forEach((attachment) => URL.revokeObjectURL(attachment.previewUrl));
      if (noticeTimeoutRef.current) clearTimeout(noticeTimeoutRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- unmount-only cleanup
  }, []);

  useImperativeHandle(ref, () => ({
    addAttachmentFile: (file: File) => addAttachments([file]),
  }));

  function addAttachments(files: File[]) {
    const images = files.filter((file) => file.type.startsWith("image/"));
    if (images.length === 0) return;
    setAttachments((current) => {
      const room = MAX_ATTACHMENTS - current.length;
      if (room <= 0) return current;
      const additions = images.slice(0, room).map((file) => {
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

  function send() {
    if (disabled) return;
    const trimmed = value.trim();
    if (!trimmed && attachments.length === 0) return;

    if (attachments.length > 0) {
      clearAttachments();
      setShowAttachmentNotice(true);
      if (noticeTimeoutRef.current) clearTimeout(noticeTimeoutRef.current);
      noticeTimeoutRef.current = setTimeout(
        () => setShowAttachmentNotice(false),
        ATTACHMENT_NOTICE_MS,
      );
    }

    if (trimmed) {
      onSend(trimmed);
      setValue("");
    }
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
      {showAttachmentNotice && (
        <p role="status" className="text-center text-xs text-text-muted">
          {copy.attachmentNotice}
        </p>
      )}
      <p className="text-center text-xs text-text-muted">
        {copy.footer}
      </p>
    </div>
  );
});
