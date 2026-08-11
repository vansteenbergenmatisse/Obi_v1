/**
 * LanguageMenu — the panel header's language switcher (PLAN 4.7.3).
 *
 * Product decision (Phase 4.7 design spec, "Copy decisions summary"): shipped as a
 * stub. All six locales render with English checked; selecting any item — including
 * English itself — only closes the menu. No real locale switch, no partial/fake
 * translation ever happens.
 */
"use client";

import { Menu } from "./menu";
import { MenuItem } from "./menu-item";

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "nl", label: "Nederlands" },
  { code: "de", label: "Deutsch" },
  { code: "fr", label: "Français" },
  { code: "es", label: "Español" },
  { code: "it", label: "Italiano" },
] as const;

const ACTIVE_LOCALE = "en";

export interface LanguageMenuProps {
  open: boolean;
  onClose: () => void;
}

export function LanguageMenu({ open, onClose }: LanguageMenuProps) {
  return (
    <Menu open={open} onClose={onClose} aria-label="Language" minWidthClassName="min-w-[190px]">
      {LANGUAGES.map((language) => {
        const active = language.code === ACTIVE_LOCALE;
        return (
          <MenuItem
            key={language.code}
            active={active}
            onSelect={onClose}
            trailing={
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.4"
                aria-hidden="true"
                className={active ? "text-accent opacity-100" : "text-accent opacity-0"}
              >
                <path d="M5 12.5l4.5 4.5L19 7.5" />
              </svg>
            }
          >
            {language.label}
          </MenuItem>
        );
      })}
    </Menu>
  );
}
