/**
 * Server-only (Node.js-only) platform registry reader for the Obi embed's CSP (PLAN 11.1c,
 * ADR-0014).
 *
 * Mirrors the backend's `active_domains()` (`apps/automation/app/platform/config/platforms.py`)
 * just enough to compute the `/embed` route's `frame-ancestors` directive at request time: reads
 * the same repo-root `config/platforms.json` (or a local override, see `PLATFORMS_PATH` below)
 * and returns the sorted, de-duplicated domain list of every `active: true` entry. Never caches —
 * each call re-reads the file, matching "computed at request time." Does not verify tokens or map
 * integrations to scopes; that stays backend-only (`TokenVerifier`/`PlatformRegistry`).
 *
 * Deliberately NOT re-exported from `./index.ts` (the feature's client-safe public root), and
 * deliberately its OWN file separate from `csp.ts`'s pure logic: this file uses real
 * `node:fs`/`node:path`/`node:url`, which cannot ship in a browser bundle OR the Edge middleware
 * runtime at all (confirmed empirically — even importing just the fs-free named exports from a
 * file that ALSO has a top-level `node:fs` import fails the Edge build). `import "server-only"`
 * below turns an accidental client import into a clear build-time error instead of the cryptic
 * webpack `UnhandledSchemeError: node:fs` this repo hit twice already. Node.js-runtime consumers
 * (`app/embed/page.tsx`, `app/api/internal/active-domains/route.ts`) import this file directly;
 * `middleware.ts` (Edge) never does — it calls the internal route instead (see its docstring).
 */
import "server-only";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
// apps/web/src/features/embed -> repo root is five directories up.
const DEFAULT_PLATFORMS_PATH = resolve(here, "../../../../../config/platforms.json");

interface RawPlatformEntry {
  domains?: string[];
  active?: boolean;
}

interface RawPlatformsFile {
  platforms?: Record<string, RawPlatformEntry>;
}

/** Same override knob name as the backend's `PLATFORMS_PATH` env var (`Settings.platforms_path`)
 * so a local dev/test setup can point both apps at one `config/platforms.local.json` with a
 * single env var (see `docs/embedding/obi-embed-local-test-keys.md`). */
function platformsPath(): string {
  const override = process.env.PLATFORMS_PATH;
  return override && override.trim() ? override : DEFAULT_PLATFORMS_PATH;
}

/** Sorted, de-duplicated domains of every `active: true` platform entry. Empty when the file has
 * no active entries, is missing, or is malformed — callers decide what an empty list means (the
 * `/embed` CSP route 403s outside local/dev, see `csp.ts`'s `computeEmbedCsp`). */
export function activeDomains(): string[] {
  let raw: RawPlatformsFile;
  try {
    raw = JSON.parse(readFileSync(platformsPath(), "utf8")) as RawPlatformsFile;
  } catch {
    return [];
  }
  const domains = new Set<string>();
  for (const entry of Object.values(raw.platforms ?? {})) {
    if (!entry.active) continue;
    for (const domain of entry.domains ?? []) domains.add(domain);
  }
  return [...domains].sort();
}
