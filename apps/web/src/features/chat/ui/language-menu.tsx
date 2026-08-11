/**
 * LanguageMenu — the panel header's language switcher (PLAN 4.7.3, made real in 4.7.7).
 *
 * Switches the widget's own six-locale UI copy (`model/i18n.ts`) for real — greeting, suggestion
 * chip, composer placeholder, footer, teaser, menu labels all follow the selected locale. Does
 * NOT translate the RAG agent's actual answers; that stays unscoped backend work (see
 * `docs/rag/OBI-WIDGET-DESIGN.md` §5).
 */
"use client";

import { Menu } from "./menu";
import { MenuItem } from "./menu-item";
import { LOCALES, LOCALE_LABELS, type Locale } from "../model/i18n";

export interface LanguageMenuProps {
  open: boolean;
  onClose: () => void;
  activeLocale: Locale;
  onSelect: (locale: Locale) => void;
}

export function LanguageMenu({ open, onClose, activeLocale, onSelect }: LanguageMenuProps) {
  return (
    <Menu open={open} onClose={onClose} aria-label="Language" minWidthClassName="min-w-[190px]">
      {LOCALES.map((code) => {
        const active = code === activeLocale;
        return (
          <MenuItem
            key={code}
            active={active}
            onSelect={() => {
              onSelect(code);
              onClose();
            }}
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
            {LOCALE_LABELS[code]}
          </MenuItem>
        );
      })}
    </Menu>
  );
}
