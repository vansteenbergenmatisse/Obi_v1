/**
 * useWidgetVisibility — the launcher/teaser timing state machine (PLAN 4.7.4).
 *
 * Mirrors the mockup's own `scheduleTeaser`/`onOpen`/`onClose`/`onDismissTeaser` behavior
 * exactly (`docs/rag/reference/obi-mockup/Obi Assistant.dc.html`): the teaser appears 3000ms
 * after mount if the panel is still closed; opening the panel cancels any pending teaser and
 * hides it; closing the panel or dismissing the teaser reschedules it to reappear after
 * 20000ms of being closed.
 */
"use client";

import { useEffect, useRef, useState } from "react";

const INITIAL_TEASER_DELAY_MS = 3000;
const REPEAT_TEASER_DELAY_MS = 20000;

export interface WidgetVisibility {
  open: boolean;
  teaser: boolean;
  openWidget: () => void;
  closeWidget: () => void;
  dismissTeaser: () => void;
}

export function useWidgetVisibility(): WidgetVisibility {
  const [open, setOpen] = useState(false);
  const [teaser, setTeaser] = useState(false);
  const openRef = useRef(open);
  openRef.current = open;
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function scheduleTeaser(delayMs: number) {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      if (!openRef.current) setTeaser(true);
    }, delayMs);
  }

  useEffect(() => {
    scheduleTeaser(INITIAL_TEASER_DELAY_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  function openWidget() {
    if (timerRef.current) clearTimeout(timerRef.current);
    setOpen(true);
    setTeaser(false);
  }

  function closeWidget() {
    setOpen(false);
    scheduleTeaser(REPEAT_TEASER_DELAY_MS);
  }

  function dismissTeaser() {
    setTeaser(false);
    scheduleTeaser(REPEAT_TEASER_DELAY_MS);
  }

  return { open, teaser, openWidget, closeWidget, dismissTeaser };
}
