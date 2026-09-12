/**
 * Frame-side bridge for the Obi embed (PLAN 11.1c, ADR-0014) — the `/embed` page's half of the
 * `postMessage` contract with `obi.js` (the host-page loader, `loader.ts`).
 *
 * Security posture (non-negotiable, this is a cross-origin embed):
 *  - Accepts `obi:token`/`obi:clear` ONLY when `event.source === window.parent` AND
 *    `event.origin` is in an explicit allow-list the caller supplies — never a wildcard, never
 *    inferred. Anything else is ignored with exactly one `console.warn`, never a thrown error
 *    (a hostile or misconfigured embedder must not be able to crash the frame).
 *  - The token lives ONLY in a module-scoped variable, reset to `null` every time
 *    `initIframeBridge` runs (a fresh frame load starts with no token) — never a cookie,
 *    `localStorage`, `sessionStorage`, or the URL.
 *  - Never logs the token value itself, only the fact that a message was accepted/rejected.
 */
import type { ObiMessage } from "@omniboost/contracts";
import { OBI_MESSAGE_TYPES } from "@omniboost/contracts";

export interface InitIframeBridgeOptions {
  /** Exact origins (scheme + host + port) allowed to drive this frame — the active platform
   * domains for this deployment. Never `"*"`. */
  allowedOrigins: string[];
  onToken?: (token: string) => void;
  onClear?: () => void;
}

let currentToken: string | null = null;

function isObiMessage(data: unknown): data is ObiMessage {
  if (typeof data !== "object" || data === null) return false;
  const type = (data as Record<string, unknown>).type;
  return typeof type === "string" && (OBI_MESSAGE_TYPES as readonly string[]).includes(type);
}

/**
 * Starts listening for `message` events from the host page. Safe to call once per frame load;
 * resets any previously held token to `null` (a reload should never carry a stale token forward).
 * Returns a teardown function that removes the listener.
 */
export function initIframeBridge(options: InitIframeBridgeOptions): () => void {
  currentToken = null;

  function handleMessage(event: MessageEvent): void {
    if (event.source !== window.parent) {
      console.warn("obi_bridge_rejected_non_parent_source");
      return;
    }
    if (!options.allowedOrigins.includes(event.origin)) {
      console.warn("obi_bridge_rejected_origin");
      return;
    }
    if (!isObiMessage(event.data)) return;

    switch (event.data.type) {
      case "obi:token":
        currentToken = event.data.token;
        options.onToken?.(event.data.token);
        return;
      case "obi:clear":
        currentToken = null;
        options.onClear?.();
        return;
      case "obi:open":
        // Carries no data (PLAN 11.1c) — the frame's own widget owns its open/teaser state;
        // no bridge-level effect today. Handled explicitly so the switch stays exhaustive.
        return;
    }
  }

  window.addEventListener("message", handleMessage);
  return () => window.removeEventListener("message", handleMessage);
}

/** The current embed token, or `null` when none has been handed over yet (or it was cleared).
 * Reads only the module-scoped variable above — never a web storage API. */
export function getToken(): string | null {
  return currentToken;
}
