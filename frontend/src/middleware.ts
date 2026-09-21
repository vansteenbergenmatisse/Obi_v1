/**
 * Per-request CSP for the Obi embed frame (PLAN 11.1c, ADR-0014).
 *
 * Scoped to `/embed` only (see `config.matcher`). Computes `frame-ancestors` from the CURRENT
 * active platform domains on every request — never cached, never `*`. An empty active-domain
 * list outside local/dev means no platform is currently authorized to frame the widget, so the
 * frame refuses to be embedded at all (403) rather than silently default-allowing any origin.
 * `computeEmbedCsp` (`features/embed/platforms.ts`) is the pure decision function, unit-testable
 * without a full request/response round trip.
 *
 * Middleware runs on the Edge runtime by default, which has no `node:fs` — and this installed
 * Next.js version (15.5.22) does not actually wire up `runtime: "nodejs"`/`experimental.
 * nodeMiddleware` despite both being nominally accepted (confirmed empirically: `next build`
 * left `middleware-manifest.json` empty either way, meaning the middleware silently never ran).
 * So the active-domain list is fetched from `/api/internal/active-domains` (a plain Node.js route
 * handler that DOES call `node:fs`, same-origin, no CORS) instead of read directly here — this
 * keeps the "computed fresh at request time from `config/platforms.json`, `PLATFORMS_PATH`-
 * override included" behavior on genuine Edge middleware, at the cost of one small internal HTTP
 * hop per `/embed` request. Revisit once Node.js middleware is verified working in a newer
 * Next.js release (see `docs/embedding/obi-embed-local-test-keys.md`).
 */
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
// Edge-safe: `csp.ts` has zero Node-only imports, unlike `platforms.ts` (`node:fs`).
import { computeEmbedCsp, isLocalOrDevEnv } from "@/features/embed/csp";

export async function middleware(request: NextRequest): Promise<NextResponse> {
  let domains: string[] = [];
  try {
    const response = await fetch(new URL("/api/internal/active-domains", request.url));
    if (response.ok) {
      const body = (await response.json()) as { domains?: unknown };
      if (Array.isArray(body.domains)) {
        domains = body.domains.filter((d): d is string => typeof d === "string");
      }
    }
  } catch {
    // Treated the same as "no active domains" below — fail toward refusing to frame, never
    // toward silently allowing everyone.
  }

  const result = computeEmbedCsp(domains, isLocalOrDevEnv());
  if (!result.ok) {
    return new NextResponse(null, { status: 403 });
  }
  const response = NextResponse.next();
  response.headers.set("Content-Security-Policy", result.header);
  return response;
}

export const config = {
  matcher: "/embed",
};
