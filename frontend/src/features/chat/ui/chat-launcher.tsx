/**
 * ChatLauncher — the closed-state floating button (PLAN 4.7.4, pixel-exact reference in
 * `docs/rag/PLAN.md` Phase 4.7's design spec, "Launcher (closed state)").
 *
 * Feature-internal, used once by `chat-widget.tsx`. Pulses with the already-built
 * `launcher-pulse` keyframe exactly while the teaser popup is visible, not otherwise.
 */
"use client";

import { AssistantMark } from "./assistant-mark";
import { useChatSession } from "./chat-session-provider";
import { getCopy } from "../model/i18n";

export interface ChatLauncherProps {
  onOpen: () => void;
  /** True exactly while the teaser popup is visible. */
  pulsing: boolean;
}

export function ChatLauncher({ onOpen, pulsing }: ChatLauncherProps) {
  const { locale } = useChatSession();
  const copy = getCopy(locale);
  return (
    <button
      type="button"
      title={copy.openAssistant}
      aria-label={copy.openAssistant}
      onClick={onOpen}
      className={[
        "fixed bottom-lg right-lg z-widget flex h-[52px] w-[52px] items-center justify-center rounded-full",
        "border border-border bg-surface-raised shadow-[0_6px_20px_rgba(35,38,59,0.16)]",
        "transition-transform duration-fast hover:scale-[1.06] hover:border-accent-secondary",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
        pulsing ? "motion-safe:animate-[launcher-pulse_2s_ease-out_infinite]" : "",
      ].join(" ")}
    >
      <AssistantMark size={24} />
    </button>
  );
}
