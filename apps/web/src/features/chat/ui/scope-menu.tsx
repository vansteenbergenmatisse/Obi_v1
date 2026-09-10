/**
 * ScopeMenu — the panel header's knowledge-scope switcher (PLAN 10.8).
 *
 * A dev/verification control (gated on in the header, see `panel-header.tsx`) that lets a tester
 * pick which recognized knowledge scope (`obi-general-test`/`obi-mews-test`/`obi-operacloud-test`/
 * `obi-toast-test`, ADR-0011) the
 * outgoing chat request carries, so the four scopes can be shown — live, in the UI — to return
 * different, isolated evidence. It sets 10.5's `knowledgeScope` request field via the session
 * context; the backend already accepts and enforces it (PLAN 10.4/10.5). A polished per-deployment
 * embed picks its scope once via the `ChatSessionProvider` prop and does NOT show this menu.
 *
 * Mirrors `LanguageMenu` exactly — same `Menu`/`MenuItem` primitives, same checkmark affordance —
 * so it stays on-brand for free rather than inventing a second dropdown style.
 */
"use client";

import { Menu } from "./menu";
import { MenuItem } from "./menu-item";
import { KNOWLEDGE_SCOPES, type KnowledgeScope } from "../model/knowledge-scopes";

export interface ScopeMenuProps {
  open: boolean;
  onClose: () => void;
  /** The scope currently applied to requests, or `undefined` for the embed/backend default. */
  activeScope: string | undefined;
  onSelect: (scope: KnowledgeScope) => void;
}

export function ScopeMenu({ open, onClose, activeScope, onSelect }: ScopeMenuProps) {
  return (
    <Menu open={open} onClose={onClose} aria-label="Knowledge scope">
      {KNOWLEDGE_SCOPES.map(({ name, label }) => {
        const active = name === activeScope;
        return (
          <MenuItem
            key={name}
            active={active}
            onSelect={() => {
              onSelect(name);
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
            {label}
          </MenuItem>
        );
      })}
    </Menu>
  );
}
