/**
 * Captures the shared widget access token (`docs/future-ideas/IDEAS.md` idea #6) from an invite
 * link and makes it available to `chat-client.ts`. `sessionStorage`, not `localStorage` —
 * deliberately tab-lifetime only, matching the "small trusted pilot, not full multi-tenant"
 * scope this token is meant for. The token is stripped from the visible URL right after capture
 * so it doesn't linger in browser history or leak via `Referer` on outbound links.
 */

const STORAGE_KEY = "obi_widget_access_token";
const QUERY_PARAM = "access_token";

/** Client-side only; a no-op during SSR. Call once per page load (e.g. on mount of the
 * app-root-level session provider) — safe to call again, it's idempotent when the URL has no
 * fresh param. */
export function captureWidgetAccessToken(): void {
  if (typeof window === "undefined") return;

  const url = new URL(window.location.href);
  const fromUrl = url.searchParams.get(QUERY_PARAM);
  if (!fromUrl) return;

  window.sessionStorage.setItem(STORAGE_KEY, fromUrl);
  url.searchParams.delete(QUERY_PARAM);
  window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
}

export function getWidgetAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.sessionStorage.getItem(STORAGE_KEY);
}
