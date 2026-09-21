/**
 * The Obi embed loader — bundled to `public/obi.js` (esbuild, IIFE, `pnpm --filter web
 * build:obi`) and served from our own domain. A platform's page adds ONE script tag pointing at
 * it, then calls `Obi.init({ tokenUrl })` (PLAN 11.1c, ADR-0014).
 *
 * Runs entirely in the HOST page's window — a completely different JS realm from the `/embed`
 * iframe's own bundle (`features/embed/iframe-bridge.ts`); the two talk only via `postMessage`,
 * exactly the three `ObiMessage` types (`@omniboost/contracts`) — `obi:open`, `obi:token`,
 * `obi:clear` — and only ever TO the iframe with `OBI_ORIGIN` as the exact `targetOrigin`, never
 * `"*"`. This module never imports `@omniboost/contracts` directly (a standalone esbuild IIFE
 * bundle, not part of the Next module graph) — the three literal type strings are inlined below
 * and kept in lockstep with that file by `packages/contracts/src/iframe-messages.ts`'s own
 * "exactly three" contract note; do not add a fourth without updating both.
 *
 * Token handling (non-negotiable): the JWT is fetched fresh at button click (not at page load or
 * login), decoded client-side ONLY for its `exp` (display/renewal timing — never trust-bearing;
 * the backend's `TokenVerifier` is the actual signature/claims verifier), held in a module-scoped
 * variable only, and forgotten on `Obi.clear()`. Never a cookie, `localStorage`,
 * `sessionStorage`, or the URL. The token value itself is never logged.
 */

export interface ObiInitOptions {
  /** Same-origin endpoint on the HOST page's own server that mints a short-lived platform-signed
   * JWT. Fetched with `credentials: "same-origin"` so the platform's own session cookie rides —
   * no CORS needed since it's same-origin from the host page's perspective. */
  tokenUrl: string;
}

// Replaced at build time by esbuild's `--define:__OBI_ORIGIN__=...` (see package.json's
// `build:obi` script, driven by the `OBI_ORIGIN` env var). Falls back to the current page's own
// origin for local dev, where obi.js and the `/embed` frame are served by the same Next.js app.
declare const __OBI_ORIGIN__: string | undefined;
const OBI_ORIGIN: string =
  typeof __OBI_ORIGIN__ !== "undefined" && __OBI_ORIGIN__ ? __OBI_ORIGIN__ : window.location.origin;

const MSG_OPEN = "obi:open";
const MSG_TOKEN = "obi:token";
const MSG_CLEAR = "obi:clear";

// Renew this long before the decoded `exp` so a click never races an about-to-expire token.
const RENEW_BEFORE_EXPIRY_MS = 60_000;
const MIN_RENEW_DELAY_MS = 1_000;

let iframeEl: HTMLIFrameElement | null = null;
let launcherEl: HTMLButtonElement | null = null;
let renewTimer: ReturnType<typeof setTimeout> | null = null;
let isOpen = false;

// The launcher renders Obi's two-tone sparkle mark (the "star"), pixel-identical to the main
// site's `ChatLauncher` (`features/chat/ui/chat-launcher.tsx` + `assistant-mark.tsx`). Values are
// the resolved design tokens (`@omniboost/design-tokens`: surfaceRaised #fff, border #e6e8ee,
// accent #635bff, accentSecondary #8f8af7) inlined here because this bundle runs in the HOST
// page's realm with no Tailwind/token access. Keep in lockstep with those two components.
const STYLE_ID = "obi-launcher-style";
const LAUNCHER_CLASS = "obi-launcher";
const STAR_SVG =
  '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">' +
  '<path d="M11 2C11.9 7.2 13.3 8.6 18.5 9.5C13.3 10.4 11.9 11.8 11 17C10.1 11.8 8.7 10.4 3.5 9.5C8.7 8.6 10.1 7.2 11 2Z" fill="#635bff"/>' +
  '<path d="M18.5 13.5C18.9 15.8 19.6 16.5 22 17C19.6 17.5 18.9 18.2 18.5 20.5C18.1 18.2 17.4 17.5 15 17C17.4 16.5 18.1 15.8 18.5 13.5Z" fill="#8f8af7"/>' +
  "</svg>";

/** Display/scheduling only — the backend is the real verifier. Malformed/unparseable tokens
 * simply never get a renewal timer scheduled (the click-time fetch already sent one). */
function decodeExpMs(token: string): number | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
    const json = JSON.parse(atob(base64)) as { exp?: number };
    return typeof json.exp === "number" ? json.exp * 1000 : null;
  } catch {
    return null;
  }
}

function postToFrame(message: { type: string } & Record<string, unknown>): void {
  iframeEl?.contentWindow?.postMessage(message, OBI_ORIGIN);
}

function scheduleRenewal(tokenUrl: string, token: string): void {
  if (renewTimer) {
    clearTimeout(renewTimer);
    renewTimer = null;
  }
  const expMs = decodeExpMs(token);
  if (expMs === null) return;
  const delay = Math.max(expMs - Date.now() - RENEW_BEFORE_EXPIRY_MS, MIN_RENEW_DELAY_MS);
  renewTimer = setTimeout(() => {
    void fetchAndSendToken(tokenUrl);
  }, delay);
}

/**
 * Fetches a fresh token and hands it to the frame. `isRetry` guards the "on a backend 401 renew
 * once" rule (PLAN 11.1c spec): a 401 here means the PLATFORM's own token-minting endpoint
 * rejected the request (e.g. its session cookie expired) — not the RAG backend, which this
 * module never talks to directly (only the `/embed` frame's own `chat-client.ts` does, over a
 * completely separate fetch in a different window). One retry, then give up silently rather than
 * loop.
 */
async function fetchAndSendToken(tokenUrl: string, isRetry = false): Promise<void> {
  let response: Response;
  try {
    response = await fetch(tokenUrl, { credentials: "same-origin" });
  } catch {
    return;
  }
  if (response.status === 401 && !isRetry) {
    await fetchAndSendToken(tokenUrl, true);
    return;
  }
  if (!response.ok) return;

  const body = (await response.json().catch(() => null)) as { token?: string } | null;
  const token = body?.token;
  if (!token) return;

  postToFrame({ type: MSG_TOKEN, token });
  scheduleRenewal(tokenUrl, token);
}

function injectIframe(): HTMLIFrameElement {
  const iframe = document.createElement("iframe");
  iframe.src = `${OBI_ORIGIN}/embed`;
  iframe.title = "Obi chat";
  // Bottom offset clears the 52px launcher (24px offset + 52px + 12px gap = 88px) so the open
  // panel floats ABOVE the launcher instead of covering its composer — the launcher stays put as
  // the single open/close toggle (the Intercom/Drift pattern), never overlapping.
  iframe.style.cssText =
    "position:fixed;bottom:88px;right:24px;width:380px;height:560px;max-height:calc(100vh - 112px);" +
    "border:0;border-radius:16px;box-shadow:0 8px 32px rgba(0,0,0,0.24);z-index:2147483646;display:none;";
  document.body.appendChild(iframe);
  return iframe;
}

// Injected once into the host page so the launcher's hover/focus states can use pseudo-classes
// (a host page has no Tailwind). Scoped to `.obi-launcher` so it can't touch host styles. Mirrors
// `ChatLauncher`'s `hover:scale-[1.06] hover:border-accent-secondary` + `focus-visible:ring`.
function ensureLauncherStyle(): void {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent =
    `.${LAUNCHER_CLASS}{position:fixed;bottom:24px;right:24px;width:52px;height:52px;` +
    "display:flex;align-items:center;justify-content:center;border-radius:9999px;" +
    "border:1px solid #e6e8ee;background:#fff;cursor:pointer;z-index:2147483647;padding:0;" +
    "box-shadow:0 6px 20px rgba(35,38,59,0.16);" +
    "transition:transform 120ms cubic-bezier(0.16,1,0.3,1),border-color 120ms cubic-bezier(0.16,1,0.3,1);}" +
    `.${LAUNCHER_CLASS}:hover{transform:scale(1.06);border-color:#8f8af7;}` +
    `.${LAUNCHER_CLASS}:focus-visible{outline:none;box-shadow:0 6px 20px rgba(35,38,59,0.16),0 0 0 2px #635bff;}`;
  document.head.appendChild(style);
}

function injectLauncherButton(onClick: () => void): HTMLButtonElement {
  ensureLauncherStyle();
  const button = document.createElement("button");
  button.type = "button";
  button.className = LAUNCHER_CLASS;
  button.setAttribute("aria-label", "Open Obi chat");
  button.setAttribute("aria-expanded", "false");
  button.innerHTML = STAR_SVG;
  button.addEventListener("click", onClick);
  document.body.appendChild(button);
  return button;
}

function showWidget(tokenUrl: string): void {
  if (iframeEl) iframeEl.style.display = "block";
  launcherEl?.setAttribute("aria-expanded", "true");
  isOpen = true;
  // The frame renders the panel directly on `obi:open` (no nested launcher) — one click, one
  // panel, exactly like the main-site widget opening.
  postToFrame({ type: MSG_OPEN });
  void fetchAndSendToken(tokenUrl);
}

/** Host-side hide only — the launcher is the single open/close control (the frame has no Close
 * chrome when embedded). Keeps the token and conversation intact so re-opening resumes; use
 * `Obi.clear()` for a real logout that forgets both. */
function hideWidget(): void {
  if (iframeEl) iframeEl.style.display = "none";
  launcherEl?.setAttribute("aria-expanded", "false");
  isOpen = false;
}

function toggleWidget(tokenUrl: string): void {
  if (isOpen) hideWidget();
  else showWidget(tokenUrl);
}

function init(options: ObiInitOptions): void {
  // Idempotent: tear down any existing widget first so a host can re-point Obi at a new tokenUrl
  // (e.g. the `/test-hosts/multi` page switching the signed-in user) without accumulating a second
  // launcher/iframe. The fresh iframe also means the previous user's in-frame conversation is gone
  // — no answer from one identity can carry over to the next.
  if (iframeEl || launcherEl) destroy();
  iframeEl = injectIframe();
  launcherEl = injectLauncherButton(() => toggleWidget(options.tokenUrl));
}

function clear(): void {
  if (renewTimer) {
    clearTimeout(renewTimer);
    renewTimer = null;
  }
  postToFrame({ type: MSG_CLEAR });
  hideWidget();
}

/** Full teardown: cancels the renewal timer and removes the launcher + iframe from the DOM,
 * resetting module state. Unlike `clear()` (which forgets the token but leaves the hidden widget
 * in place to re-open), this leaves no Obi elements behind — used to re-init cleanly under a
 * different tokenUrl, and available to hosts that need to fully unmount the widget. */
function destroy(): void {
  if (renewTimer) {
    clearTimeout(renewTimer);
    renewTimer = null;
  }
  iframeEl?.remove();
  launcherEl?.remove();
  iframeEl = null;
  launcherEl = null;
  isOpen = false;
}

declare global {
  interface Window {
    Obi: { init: typeof init; clear: typeof clear; destroy: typeof destroy };
  }
}

window.Obi = { init, clear, destroy };
