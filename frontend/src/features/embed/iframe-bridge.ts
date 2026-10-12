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
 * `TokenVerifier` is the authority). Kept in memory only, alongside `currentToken`. `slots` is a
 * stable signature of the §D.13 three-slot integration context (substep 8.4.2) — present when the
 * note carries the extended `context.slots` shape, `null` for a legacy single-integration note.
 * `source`/`target` are the directed-connection endpoints (substep 9.3.1, ADR-0020 Option A) —
 * present when the note carries the `source_system`/`target_system` form, `null` otherwise. They
 * join the signature so a silent renewal that switches the connection (even a direction swap:
 * toast→mews vs mews→toast) counts as a scope change and resets the thread (no cross-connection
 * bleed). */
interface TokenScope {
  integration: string | null;
  company: string | null;
  slots: string | null;
  source: string | null;
  target: string | null;
}

let currentScope: TokenScope | null = null;

/** A stable, order-independent signature of the three §D.13 slots, or `null` when the note carries
 * no `context.slots` (a legacy single-integration note). Only used to tell whether a renewal
 * crossed into a different integration context — never for trust. */
function slotsSignature(context: unknown): string | null {
  if (typeof context !== "object" || context === null) return null;
  const slots = (context as Record<string, unknown>).slots;
  if (typeof slots !== "object" || slots === null) return null;
  const s = slots as Record<string, unknown>;
  const read = (key: string): string => (typeof s[key] === "string" ? (s[key] as string) : "");
  // Fixed key order (pos, pms, accounting) so the signature is deterministic regardless of the
  // JSON's property order.
  return `pos=${read("pos")};pms=${read("pms")};accounting=${read("accounting")}`;
}

/** Decodes the (untrusted, display-only) `integration` + `company_id` + `context.slots` claims
 * from a token's payload — enough to tell whether a renewal changed which corpus/identity the note
 * is scoped to (substep 8.4.2 extends this past the legacy single `integration` claim; see
 * `packages/contracts/src/token-claims.json`). Never throws; an unparseable or claimless token
 * yields nulls, which compare equal to another claimless token (both scope to general). */
const EMPTY_SCOPE: TokenScope = {
  integration: null,
  company: null,
  slots: null,
  source: null,
  target: null,
};

function decodeScope(token: string): TokenScope {
  try {
    const payload = token.split(".")[1];
    if (!payload) return { ...EMPTY_SCOPE };
    const json = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/"))) as {
      integration?: unknown;
      company_id?: unknown;
      context?: unknown;
      source_system?: unknown;
      target_system?: unknown;
      business_id?: unknown;
    };
    const str = (v: unknown): string | null => (typeof v === "string" ? v : null);
    return {
      integration: str(json.integration),
      // The directed form carries `business_id` (≈ company_id) instead of `company_id`; either
      // one identifies the customer this note is scoped to.
      company: str(json.company_id) ?? str(json.business_id),
      slots: slotsSignature(json.context),
      source: str(json.source_system),
      target: str(json.target_system),
    };
  } catch {
    return { ...EMPTY_SCOPE };
  }
}

function sameScope(a: TokenScope, b: TokenScope): boolean {
  return (
    a.integration === b.integration &&
    a.company === b.company &&
    a.slots === b.slots &&
    a.source === b.source &&
    a.target === b.target
  );
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
