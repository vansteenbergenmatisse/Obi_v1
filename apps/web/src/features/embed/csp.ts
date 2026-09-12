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

const _LOCAL_ENVS = new Set(["local", "dev", "development", "test", "ci"]);

/**
 * True in local/dev/test/ci — envs where an empty active-domain list is tolerated (there's simply
 * nothing configured yet) rather than a real deployment gap. Checks the explicit `APP_ENV` first
 * (so ops/tests can force either branch deterministically); falls back to `NODE_ENV !== "production"`
 * when `APP_ENV` is unset, matching the conservative "assume non-prod unless told otherwise" default
 * everywhere else in this app.
 */
export function isLocalOrDevEnv(): boolean {
  const explicit = process.env.APP_ENV?.trim().toLowerCase();
  if (explicit) return _LOCAL_ENVS.has(explicit);
  return process.env.NODE_ENV !== "production";
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
 */
export function computeEmbedCsp(domains: string[], isLocalOrDev: boolean): EmbedCspResult {
  if (domains.length === 0 && !isLocalOrDev) {
    return { ok: false, header: "frame-ancestors 'none'" };
  }
  const ancestors = domains.length > 0 ? domains.join(" ") : "'none'";
  return { ok: true, header: `frame-ancestors ${ancestors}` };
}
