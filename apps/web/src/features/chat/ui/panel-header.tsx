/**
 * PanelHeader — the widget/panel chrome bar (PLAN 4.7.3): assistant mark + name,
 * and the "···" / language / close icon row. Owns the two menus' open state
 * (mutually exclusive — opening one closes the other) and renders them as
 * siblings of the header bar so they anchor to `panel-body.tsx`'s positioned
 * root rather than this header's own 52px height.
 *
 * The mockup always shows a Close icon, but a full-page route has nothing to
 * close — `onClose` is optional and the icon only renders when a real close
 * handler exists (the floating `ChatWidget`, PLAN 4.7.4), so nothing here
 * pretends to work that doesn't.
 */
"use client";

import { useState } from "react";
import { AssistantMark } from "./assistant-mark";
import { IconButton } from "./icon-button";
import { LanguageMenu } from "./language-menu";
import { Menu } from "./menu";
import { MenuItem } from "./menu-item";
import { useChatSession } from "./chat-session-provider";
import { getCopy } from "../model/i18n";

export interface PanelHeaderProps {
  /** "Obi" is the mockup's placeholder name, not a confirmed product decision. */
  assistantName?: string;
  onRestart: () => void;
  onClose?: () => void;
  /** Captures the page behind the widget and drops it into the composer as an attachment
   * (PLAN 4.7.7). Real capture, but — same as any other image attachment — nothing analyzes it
   * yet; see the composer's send-time notice. Optional only so header tests that don't care about
   * screenshots stay simple; the real widget always passes it. */
  onScreenshot?: () => void;
}

export function PanelHeader({
  assistantName = "Obi",
  onRestart,
  onClose,
  onScreenshot,
}: PanelHeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [langOpen, setLangOpen] = useState(false);
  const { locale, setLocale } = useChatSession();
  const copy = getCopy(locale);

  function toggleMenu() {
    setLangOpen(false);
    setMenuOpen((open) => !open);
  }

  function toggleLang() {
    setMenuOpen(false);
    setLangOpen((open) => !open);
  }

  function closeMenus() {
    setMenuOpen(false);
    setLangOpen(false);
  }

  return (
    <>
      <header className="relative z-widget flex h-[52px] flex-none items-center gap-sm border-b border-border bg-surface-raised pl-[16px] pr-[14px]">
        <AssistantMark size={20} />
        <span className="text-[15px] font-semibold text-text">{assistantName}</span>
        <div className="ml-auto flex items-center gap-[2px]">
          <IconButton
            aria-label={copy.more}
            title={copy.more}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            active={menuOpen}
            onClick={toggleMenu}
            className="h-[30px] w-[30px]"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <circle cx="5" cy="12" r="1.7" />
              <circle cx="12" cy="12" r="1.7" />
              <circle cx="19" cy="12" r="1.7" />
            </svg>
          </IconButton>
          {onScreenshot ? (
            <IconButton
              aria-label={copy.screenshot}
              title={copy.screenshot}
              onClick={onScreenshot}
              className="h-[30px] w-[30px]"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                aria-hidden="true"
              >
                <path d="M3 8V5a2 2 0 0 1 2-2h3M16 3h3a2 2 0 0 1 2 2v3M21 16v3a2 2 0 0 1-2 2h-3M8 21H5a2 2 0 0 1-2-2v-3" />
                <circle cx="12" cy="12" r="3.2" />
              </svg>
            </IconButton>
          ) : null}
          <IconButton
            aria-label={copy.language}
            title={copy.language}
            aria-haspopup="menu"
            aria-expanded={langOpen}
            active={langOpen}
            onClick={toggleLang}
            className="h-[30px] w-[30px]"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="9" />
              <path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
            </svg>
          </IconButton>
          {onClose ? (
            <IconButton
              aria-label={copy.close}
              title={copy.close}
              onClick={onClose}
              className="h-[30px] w-[30px]"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
              >
                <path d="M6 6l12 12M18 6L6 18" />
              </svg>
            </IconButton>
          ) : null}
        </div>
      </header>

      <Menu open={menuOpen} onClose={closeMenus} aria-label="More options">
        <MenuItem disabled>{copy.docs}</MenuItem>
        <MenuItem disabled>{copy.support}</MenuItem>
        <MenuItem
          danger
          onSelect={() => {
            onRestart();
            closeMenus();
          }}
        >
          {copy.restart}
        </MenuItem>
      </Menu>

      <LanguageMenu
        open={langOpen}
        onClose={closeMenus}
        activeLocale={locale}
        onSelect={setLocale}
      />
    </>
  );
}
