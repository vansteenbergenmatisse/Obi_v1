/**
 * Obi `/embed` frame page (PLAN 11.1c, ADR-0014) — server component so it can read the active
 * platform registry (`features/embed`'s `activeDomains`, node `fs`-backed) without shipping that
 * read into the client bundle. Turns bare domains (`config/platforms.json`'s `domains`, e.g.
 * `"app.mews.com"`) into full origins for the frame-side bridge's allow-list — both schemes are
 * generated per domain (a real production entry is always `https`; local/test entries commonly
 * run on plain `http://localhost:<port>`) since the security value is the domain allow-list
 * itself, already vetted by `platforms.json`'s `active: true` entries, not the scheme.
 *
 * The route's `Content-Security-Policy: frame-ancestors` is set per-request by `middleware.ts`,
 * not here — this file only renders the frame's content.
 */
// Server-only (`node:fs`) — imported directly from `features/embed/platforms`, NOT the feature's
// client-safe `@/features/embed` barrel (see that file's docstring).
import { activeDomains } from "@/features/embed/platforms";
import { EmbedFrame } from "./embed-frame";

function toOrigins(domains: string[]): string[] {
  return domains.flatMap((domain) => [`https://${domain}`, `http://${domain}`]);
}

export default function EmbedPage() {
  const allowedOrigins = toOrigins(activeDomains());
  return <EmbedFrame allowedOrigins={allowedOrigins} />;
}
