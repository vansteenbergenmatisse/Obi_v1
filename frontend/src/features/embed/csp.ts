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
 * The set of edge-whitespace code points to strip from a host before matching — the twin of the
 * backend's `_EDGE_WHITESPACE` in `platforms.py` (gap W8-A1-1). Bare JS `String.prototype.trim()`
 * and Python `str.strip()` remove DIFFERENT characters (Python also strips C1 separators U+001C–
 * U+001F and NEL U+0085; JS also strips the BOM U+FEFF), which made this matcher diverge from its
 * backend twin on those six code points. Both sides now strip this ONE identical union set, so a
 * malformed edge character can no longer let a loopback host slip past one side but not the other.
 */
const EDGE_WHITESPACE = new Set([
  0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x20, // tab LF VT FF CR space  (both runtimes strip)
  0xa0, 0x1680, // NBSP, Ogham space  (both)
  0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008, 0x2009, 0x200a, // en..hair
  0x2028, 0x2029, 0x202f, 0x205f, 0x3000, // line/para sep, narrow/med NBSP, ideographic  (both)
  0x1c, 0x1d, 0x1e, 0x1f, 0x85, // FS GS RS US NEL  (Python str.strip only)
  0xfeff, // BOM / zero-width no-break space  (JS trim only)
]);

/** Strip the shared `EDGE_WHITESPACE` union set from both ends — the twin of the backend
 * `_strip_edges`. Used instead of bare `.trim()` so the two host matchers stay in step (gap
 * W8-A1-1). All members are BMP single code units, so index-based iteration is exact. */
function stripEdges(value: string): string {
  let start = 0;
  let end = value.length;
  while (start < end && EDGE_WHITESPACE.has(value.charCodeAt(start))) start++;
  while (end > start && EDGE_WHITESPACE.has(value.charCodeAt(end - 1))) end--;
  return value.slice(start, end);
}

/** A `127.0.0.0/8` IPv4 loopback literal — `127.` followed by three numeric octets, each 0–255.
 * Deliberately a strict numeric-IPv4 check so a hostname that merely starts with `127.`
 * (e.g. `127.example.com`) is NOT treated as loopback (gap BIT-A-R1). */
function isIpv4LoopbackHost(host: string): boolean {
  const octets = host.split(".");
  if (octets.length !== 4) return false;
  if (!octets.every((o) => /^\d{1,3}$/.test(o) && Number(o) <= 255)) return false;
  return octets[0] === "127";
}

/**
 * Expand an IPv6 literal to its eight 16-bit groups, or `null` when `host` is not a well-formed
 * IPv6 address. Handles `::` zero-compression and a trailing dotted-quad IPv4 (`::ffff:127.0.0.1`).
 * Hand-rolled (no runtime dep) so the logic is IDENTICAL to the backend's `_expand_ipv6` twin in
 * `platforms.py` (gap BIT-LOOPBACK-EDGE-1) — a divergence between the two is the recurring bug.
 */
function expandIpv6(host: string): number[] | null {
  if (!host.includes(":")) return null;
  if ((host.match(/::/g)?.length ?? 0) > 1) return null;
  let work = host;
  if (work.includes(".")) {
    const idx = work.lastIndexOf(":");
    if (idx === -1) return null;
    const head = work.slice(0, idx + 1);
    const v4 = work.slice(idx + 1);
    const octets = v4.split(".");
    if (octets.length !== 4) return null;
    const vals: number[] = [];
    for (const o of octets) {
      if (!/^\d{1,3}$/.test(o)) return null;
      const n = Number(o);
      if (n > 255) return null;
      vals.push(n);
    }
    const hex = (n: number) => n.toString(16).padStart(2, "0");
    work = `${head}${hex(vals[0])}${hex(vals[1])}:${hex(vals[2])}${hex(vals[3])}`;
  }
  let groups: string[];
  if (work.includes("::")) {
    const [left, right] = work.split("::");
    const lg = left ? left.split(":") : [];
    const rg = right ? right.split(":") : [];
    if (lg.some((g) => g === "") || rg.some((g) => g === "")) return null;
    const missing = 8 - (lg.length + rg.length);
    if (missing < 1) return null; // `::` must stand for at least one all-zero group
    groups = [...lg, ...Array<string>(missing).fill("0"), ...rg];
  } else {
    groups = work.split(":");
  }
  if (groups.length !== 8) return null;
  const out: number[] = [];
  for (const g of groups) {
    if (!/^[0-9a-f]{1,4}$/.test(g)) return null;
    out.push(parseInt(g, 16));
  }
  return out;
}

/** True for an IPv6 loopback literal in any form (gap BIT-LOOPBACK-EDGE-1): compressed `::1`,
 * fully-expanded `0:0:0:0:0:0:0:1`, and IPv4-mapped `::ffff:<127.0.0.0/8>` (dotted `::ffff:127.0.0.1`
 * or hex `::ffff:7f00:1`). Does NOT match a real IPv6 host or the deprecated non-mapped `::7f00:1`.
 * Mirrors the backend's `_is_ipv6_loopback`. */
function isIpv6Loopback(host: string): boolean {
  const groups = expandIpv6(host);
  if (groups === null) return false;
  if (groups.slice(0, 7).every((g) => g === 0) && groups[7] === 1) return true;
  // IPv4-mapped (::ffff:a.b.c.d): the mapped IPv4's first octet in the 127.0.0.0/8 block.
  return (
    groups.slice(0, 5).every((g) => g === 0) && groups[5] === 0xffff && groups[6] >> 8 === 0x7f
  );
}

/**
 * A bare `host[:port]` CSP domain that must be stripped OUTSIDE local/dev — the local loopback
 * (gap CFG-04, widened for gaps BIT-A-R1 + BIT-LOOPBACK-EDGE-1) OR an mDNS `.local` TLD name (gap
 * CFG-DOMLOCAL-1). Domains are stored without a scheme (e.g. `"localhost:3000"`, `"app.mews.com"`,
 * `"[::1]:3000"`, `"app.acme.local"`). A pure host check that treats the FULL non-production set as
 * local so none of it can become a trusted embedder origin / frame-ancestor outside local/dev:
 *  - `localhost` and any `*.localhost`;
 *  - the trailing-dot FQDN root form of any of these (`localhost.`, `127.0.0.1.`);
 *  - the whole `127.0.0.0/8` block (`127.x.x.x` with valid octets), not just `127.0.0.1`;
 *  - the `0.0.0.0` wildcard-bind address;
 *  - IPv6 loopback in any form: `::1`, fully-expanded `0:0:0:0:0:0:0:1`, and IPv4-mapped
 *    `::ffff:127.0.0.1` / `::ffff:7f00:1` — bare or bracketed with a port (`[::1]:3000`);
 *  - a `.local` TLD host (`app.acme.local`) — an exact `.local` suffix, so `example.local.com`
 *    and `127.example.com` are NOT over-matched.
 * A trailing `:port` is stripped only when unambiguous: bracketed IPv6 uses the text inside `[...]`,
 * a bare IPv6 literal (more than one `:`) is left whole, and a plain `host[:port]` drops one
 * `:port`. Kept in step with the backend's `_is_loopback_host` + `_is_dot_local_host` in
 * `platforms.py` (the two twins must agree — a divergence here is the recurring bug).
 */
export function isLocalhostDomain(domain: string): boolean {
  const raw = stripEdges(domain).toLowerCase();
  if (raw === "") return false;

  let host: string;
  if (raw.startsWith("[")) {
    // Bracketed IPv6: `[host]` or `[host]:port` — the host is the text between the brackets.
    const close = raw.indexOf("]");
    host = close === -1 ? raw.slice(1) : raw.slice(1, close);
  } else if ((raw.match(/:/g)?.length ?? 0) > 1) {
    // A bare IPv6 literal (multiple colons) — never strip a "port".
    host = raw;
  } else {
    // Plain `host` or `host:port` — drop a single trailing `:port`.
    host = raw.split(":")[0];
  }

  // Strip whitespace the extraction can leave INSIDE the value (`[ ::1]` → ` ::1`, `127.0.0.1 :80`
  // → `127.0.0.1 `), mirroring the backend twin `_is_loopback_host`'s unconditional strip in
  // platforms.py — using the SAME union set as the entry strip so the two matchers stay in step
  // across every edge whitespace code point (gaps W7-A1-1, W8-A1-1).
  host = stripEdges(host);

  // Normalize a single trailing FQDN dot (`localhost.`, `127.0.0.1.`, `acme.local.`).
  if (host.endsWith(".") && !host.endsWith("..")) host = host.slice(0, -1);

  if (host === "localhost" || host.endsWith(".localhost")) return true;
  if (host.endsWith(".local")) return true; // gap CFG-DOMLOCAL-1: exact `.local` TLD
  if (host === "0.0.0.0") return true;
  if (isIpv6Loopback(host)) return true;
  return isIpv4LoopbackHost(host);
}

/**
 * The active platform domains that may actually embed/drive the frame in THIS environment — the
 * single source of truth shared by BOTH consumers of `activeDomains()` (gap BIT-A1): the CSP's
 * `frame-ancestors` (`computeEmbedCsp`) and the postMessage allow-list the frame accepts messages
 * from (`app/embed/page.tsx`'s `toEmbedderOrigins`). Outside local/dev every localhost/loopback and
 * `.local` domain is stripped (a production frame must never trust the loopback or an mDNS `.local`
 * name — gaps CFG-04, BIT-LOOPBACK-EDGE-1, CFG-DOMLOCAL-1); local/dev keeps them for the embed test
 * flow. Routing both consumers through here is what keeps the CSP and the bridge
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
