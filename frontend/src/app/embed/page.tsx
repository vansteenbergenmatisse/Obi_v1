/**
 * Obi `/embed` frame page (PLAN 11.1c, ADR-0014) — server component so it can read the active
 * platform registry (`features/embed`'s `activeDomains`, node `fs`-backed) without shipping that
 * read into the client bundle. Turns bare domains (`knowledge-base/config/platforms.json`'s `domains`, e.g.
 * `"app.mews.com"`) into full origins for the frame-side bridge's allow-list via the SHARED
 * `toEmbedderOrigins` (`csp.ts`) so the bridge allow-list can never diverge from the CSP's
 * `frame-ancestors` (gap BIT-A1). Outside local/dev that helper strips every localhost/127.0.0.1
 * domain and emits `https://` only — a production frame must never trust the loopback or a
 * plaintext-`http` embedder. In local/dev both schemes stay (the embed test flow runs on plain
 * `http://localhost:<port>`).
 *
 * The route's `Content-Security-Policy: frame-ancestors` is set per-request by `middleware.ts`,
 * not here — this file only renders the frame's content.
 */
// Server-only (`node:fs`) — imported directly from `features/embed/platforms`, NOT the feature's
// client-safe `@/features/embed` barrel (see that file's docstring). `csp.ts` is Edge/pure with no
// Node-only imports, so importing the shared origins builder + env signal from it is safe here and
// matches how `middleware.ts` consumes the same module.
import { activeDomains } from "@/features/embed/platforms";
import { isLocalOrDevEnv, toEmbedderOrigins } from "@/features/embed/csp";
import { EmbedFrame } from "./embed-frame";

export default function EmbedPage() {
  const allowedOrigins = toEmbedderOrigins(activeDomains(), isLocalOrDevEnv());
  return <EmbedFrame allowedOrigins={allowedOrigins} />;
}
