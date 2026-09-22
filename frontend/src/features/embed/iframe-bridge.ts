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
  onOpen?: () => void;
  onToken?: (token: string) => void;
  onClear?: () => void;
  /** Fired when an `obi:token` REPLACES an existing token whose business scope (integration /
   * company) differs from the incoming one — a silent renewal that crossed into a different
   * corpus/identity (LC-2/LC-3/LC-6). The open conversation must be reset so no answer built for
   * one company/integration bleeds into another. Not fired for the first token of a session (no
   * prior scope to differ from). */
  onScopeChange?: () => void;
}

let currentToken: string | null = null;

/** Display/equality-only business scope decoded from a token (never trust-bearing — the backend
 * `TokenVerifier` is the authority). Kept in memory only, alongside `currentToken`. */
interface TokenScope {
  integration: string | null;
  company: string | null;
}

let currentScope: TokenScope | null = null;

/** Decodes the (untrusted, display-only) `integration` + `company_id` claims from a token's
 * payload — enough to tell whether a renewal changed which corpus/identity the note is scoped to
 * (see `packages/contracts/src/token-claims.json`). Never throws; an unparseable or claimless
 * token yields nulls, which compare equal to another claimless token (both scope to general). */
function decodeScope(token: string): TokenScope {
  try {
    const payload = token.split(".")[1];
    if (!payload) return { integration: null, company: null };
    const json = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/"))) as {
      integration?: unknown;
      company_id?: unknown;
    };
    return {
      integration: typeof json.integration === "string" ? json.integration : null,
      company: typeof json.company_id === "string" ? json.company_id : null,
    };
  } catch {
    return { integration: null, company: null };
  }
}

function sameScope(a: TokenScope, b: TokenScope): boolean {
  return a.integration === b.integration && a.company === b.company;
}

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
  currentScope = null;

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
      case "obi:token": {
        // BIT-7: `isObiMessage` only checks `type`, so `token` is TS-narrowed but not
        // runtime-checked — a hostile/misconfigured parent could post `obi:token` with a
        // missing or non-string token. Require a non-empty string before storing; drop
        // otherwise (silently, matching the no-throw posture for a bad embedder).
        const token: unknown = event.data.token;
        if (typeof token !== "string" || token === "") return;
        const nextScope = decodeScope(token);
        // LC-2/LC-3/LC-6: only when REPLACING an existing token whose scope differs.
        const scopeChanged =
          currentToken !== null && currentScope !== null && !sameScope(currentScope, nextScope);
        currentToken = token;
        currentScope = nextScope;
        options.onToken?.(token);
        if (scopeChanged) options.onScopeChange?.();
        return;
      }
      case "obi:clear":
        currentToken = null;
        currentScope = null;
        options.onClear?.();
        return;
      case "obi:open":
        // Carries no data (PLAN 11.1c). The host launcher is the single open/close control, so
        // the frame opens its panel directly here rather than showing a second, nested launcher.
        options.onOpen?.();
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
