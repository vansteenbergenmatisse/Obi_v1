/**
 * Pure, Edge-runtime-safe CSP decision logic for the Obi `/embed` frame (PLAN 11.1c, ADR-0014).
 *
 * Deliberately split out of `platforms.ts`: that file's `activeDomains()` needs real
 * `node:fs`/`node:path`/`node:url`, which cannot be bundled AT ALL for `middleware.ts` (Edge
 * runtime by default — confirmed empirically, see `middleware.ts`'s docstring). Even importing
 * ONLY `computeEmbedCsp`/`isLocalOrDevEnv` from a file that ALSO has a top-level `node:fs` import
 * still fails the Edge build (webpack must resolve every static import in a module before any
 * tree-shaking can happen) — so this logic lives in its own file with zero Node-only imports.
 */

/**
 * The accepted `APP_ENV` values that count as local/dev/test/CI for this frontend (gap CFG-H).
 *
 * This set is intentionally NOT claimed to be identical to the backend's `_OFFLINE_ENVS`
 * (`backend/app/platform/config/settings.py`). The two apps read different vars with different
 * defaults and different production signals, and each fails closed on its own terms:
 *  - Backend: `ENV` defaults to "" and is treated as PRODUCTION when unset/unknown — only an
 *    explicit `local`/`test`/`ci` label relaxes its platform-trust guard (`dev`/`development` are
 *    NOT offline there).
 *  - Frontend: the real production signal is `NODE_ENV=production` (set by Next); `APP_ENV` is only
 *    an explicit override, and `isLocalOrDevEnv()` falls back to `NODE_ENV !== "production"` when
 *    `APP_ENV` is unset. `"development"` stays in this local/dev set because that is Next's own
 *    dev `NODE_ENV`, so `dev`/`development` relaxation is a frontend concern only.
 * A contract test on each side pins its own set; the earlier "identical cross-side contract" claim
 * is retired.
 */
export const LOCAL_OR_DEV_ENVS: ReadonlySet<string> = new Set([
  "local",
  "dev",
  "development",
  "test",
  "ci",
]);

/**
 * True in local/dev/test/ci — envs where an empty active-domain list is tolerated (there's simply
 * nothing configured yet) rather than a real deployment gap. Checks the explicit `APP_ENV` first
 * (so ops/tests can force either branch deterministically); falls back to `NODE_ENV !== "production"`
 * when `APP_ENV` is unset, matching the conservative "assume non-prod unless told otherwise" default
 * everywhere else in this app.
 */
export function isLocalOrDevEnv(): boolean {
  const explicit = process.env.APP_ENV?.trim().toLowerCase();
  if (explicit) return LOCAL_OR_DEV_ENVS.has(explicit);
  return process.env.NODE_ENV !== "production";
}

/**
 * A bare `host[:port]` CSP domain that resolves to the local loopback (gap CFG-04). Domains are
 * stored without a scheme (e.g. `"localhost:3000"`, `"app.mews.com"`), so strip any `:port` before
 * comparing. Kept in step with the backend's `_LOCALHOST_HOSTS` guard in `platforms.py`.
 */
function isLocalhostDomain(domain: string): boolean {
  const host = domain.trim().toLowerCase().split(":")[0];
  return host === "localhost" || host === "127.0.0.1";
}

/**
 * The active platform domains that may actually embed/drive the frame in THIS environment — the
 * single source of truth shared by BOTH consumers of `activeDomains()` (gap BIT-A1): the CSP's
 * `frame-ancestors` (`computeEmbedCsp`) and the postMessage allow-list the frame accepts messages
 * from (`app/embed/page.tsx`'s `toEmbedderOrigins`). Outside local/dev every localhost/127.0.0.1
 * domain is stripped (a production frame must never trust the loopback); local/dev keeps them for
 * the embed test flow. Routing both consumers through here is what keeps the CSP and the bridge
 * allow-list from ever diverging — previously only `computeEmbedCsp` filtered, so the bridge
 * trusted localhost embedders in production.
 */
export function effectiveEmbedderDomains(domains: string[], isLocalOrDev: boolean): string[] {
  return isLocalOrDev ? domains : domains.filter((d) => !isLocalhostDomain(d));
}

/**
 * The exact host-page origins the frame's postMessage bridge accepts messages from, built from the
 * active platform domains (gap BIT-A1). Outside local/dev this emits ONLY `https://` origins for
 * real domains and NO loopback origin at all — a production frame must never accept postMessages
 * from localhost or over plaintext `http://`. In local/dev both schemes are emitted for every
 * domain (the embed test flow runs on plain `http://localhost:<port>`). Never `"*"`.
 */
export function toEmbedderOrigins(domains: string[], isLocalOrDev: boolean): string[] {
  return effectiveEmbedderDomains(domains, isLocalOrDev).flatMap((domain) =>
    isLocalOrDev ? [`https://${domain}`, `http://${domain}`] : [`https://${domain}`],
  );
}

export interface EmbedCspResult {
  /** `false` means the caller must respond 403 instead of serving `/embed` at all. */
  ok: boolean;
  /** The `Content-Security-Policy` header value to send when `ok` is true. */
  header: string;
}

/**
 * Pure decision function behind the `/embed` CSP (kept separate from `middleware.ts` so it's
 * trivially unit-testable without a Next.js request/response round trip). Never emits `*`: zero
 * active domains renders `frame-ancestors 'none'` when tolerated (local/dev), or fails the request
 * entirely (`ok: false`) outside it — the frame must refuse to be embedded by anyone rather than
 * silently default-allow.
 *
 * gap CFG-04 (defense in depth): outside local/dev, any localhost/127.0.0.1 domain is stripped
 * before it can reach `frame-ancestors` — a production frame must never be embeddable from the
 * loopback. The backend registry guard (`platforms.py`) already refuses such a domain at load, so
 * a well-formed prod config never carries one; this is the second layer. Local/dev keeps localhost
 * domains intact (the embed test flow).
 */
export function computeEmbedCsp(domains: string[], isLocalOrDev: boolean): EmbedCspResult {
  const effective = effectiveEmbedderDomains(domains, isLocalOrDev);
  if (effective.length === 0 && !isLocalOrDev) {
    return { ok: false, header: "frame-ancestors 'none'" };
  }
  const ancestors = effective.length > 0 ? effective.join(" ") : "'none'";
  return { ok: true, header: `frame-ancestors ${ancestors}` };
}
