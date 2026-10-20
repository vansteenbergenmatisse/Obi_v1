/**
 * Browser proof for the source-enablement hide (ADR-0023; panel mi-gate).
 * Mirrors `widget-mounts.spec.ts`, but against the `/test-hosts/quickbooks` stub, whose token route
 * mints a DIRECTED note with `source_system: "quickbooks-online"` — an accounting product NOT in
 * `product_catalog.json`'s `enabled_sources` (`["mews","toast","opera-cloud"]`, baked into
 * `public/obi.js` by `build:obi`'s `--define:__OBI_ENABLED_SOURCES__`). The loader fetches that note
 * at `init()`, decodes the (display-only) source, sees it is not enabled, and never mounts: the
 * launcher count is 0 — no launcher, no iframe, no flash.
 *
 * SIGNED-KEY CAVEAT (same class as `widget-mounts.spec.ts`, stronger here): this proof needs a real
 * minted token, so it requires `TEST_OBI_PRIVATE_KEY_QUICKBOOKS` (RS256, gitignored, see
 * `docs/embedding/obi-embed-local-test-keys.md`) in `frontend/.env.local`. WITHOUT that key the
 * token route 503s, the loader's eligibility fetch fails, and it FAILS OPEN (mounts) — the right
 * production behavior (the server-authoritative `/chat/visibility` probe is the real gate) but it
 * makes this launcher-count-0 assertion fail. So this spec is written and committed but only passes
 * where the signing key is configured; it is not run in key-less CI, exactly like `widget-mounts`
 * does not click (which would need the `none` key).
 */
import { expect, test } from "@playwright/test";

test("the obi widget stays hidden when the directed source is not enabled", async ({ page }) => {
  await page.goto("/test-hosts/quickbooks");

  // The load-time eligibility fetch + decode runs after `Obi.init()`; give it room to resolve
  // (or, without a signing key, to fail open — see the caveat above).
  await page.waitForTimeout(750);

  // No launcher and no iframe were ever mounted.
  await expect(page.locator(".obi-launcher")).toHaveCount(0);
  await expect(page.locator('iframe[title="Obi chat"]')).toHaveCount(0);
});
