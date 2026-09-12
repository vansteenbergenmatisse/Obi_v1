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
let renewTimer: ReturnType<typeof setTimeout> | null = null;

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
  iframe.style.cssText =
    "position:fixed;bottom:24px;right:24px;width:380px;height:560px;max-height:80vh;border:0;" +
    "border-radius:16px;box-shadow:0 8px 32px rgba(0,0,0,0.24);z-index:2147483646;display:none;";
  document.body.appendChild(iframe);
  return iframe;
}

function injectLauncherButton(onClick: () => void): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.setAttribute("aria-label", "Open Obi chat");
  button.style.cssText =
    "position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:9999px;" +
    "border:0;cursor:pointer;z-index:2147483647;background:#111;color:#fff;font:600 14px sans-serif;";
  button.textContent = "Obi";
  button.addEventListener("click", onClick);
  document.body.appendChild(button);
  return button;
}

function openWidget(tokenUrl: string): void {
  if (iframeEl) iframeEl.style.display = "block";
  postToFrame({ type: MSG_OPEN });
  void fetchAndSendToken(tokenUrl);
}

function init(options: ObiInitOptions): void {
  iframeEl = injectIframe();
  injectLauncherButton(() => openWidget(options.tokenUrl));
}

function clear(): void {
  if (renewTimer) {
    clearTimeout(renewTimer);
    renewTimer = null;
  }
  postToFrame({ type: MSG_CLEAR });
  if (iframeEl) iframeEl.style.display = "none";
}

declare global {
  interface Window {
    Obi: { init: typeof init; clear: typeof clear };
  }
}

window.Obi = { init, clear };
