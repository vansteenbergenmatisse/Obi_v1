/**
 * Browser smoke test (substep 0.5.1). Loads the `/test-hosts/none` stub host page — a real
 * Next.js route that renders nothing but `obi.js`'s own paste template (see
 * `playwright.config.ts`'s docstring) — and asserts the widget's launcher button and chat iframe
 * are injected into the host page's DOM, exactly what `Obi.init()` does on page load
 * (`src/features/embed/index.ts`'s `injectLauncherButton` / `injectIframe`).
 *
 * Deliberately does NOT click the launcher: a click triggers `fetchAndSendToken`, a real fetch to
 * `/api/test-hosts/none/obi-token`, which needs a local RS256 signing key configured in
 * `apps/web/.env.local` (gitignored, not something this suite can assume) — so this test proves
 * exactly what's true without a live backend: the widget mounts.
 */
import { expect, test } from "@playwright/test";

test("the obi widget mounts on a stub host page", async ({ page }) => {
  await page.goto("/test-hosts/none");

  const launcher = page.locator(".obi-launcher");
  await expect(launcher).toBeVisible();
  await expect(launcher).toHaveAttribute("aria-label", "Open Obi chat");

  const frame = page.locator('iframe[title="Obi chat"]');
  await expect(frame).toHaveCount(1);
  await expect(frame).toHaveAttribute("src", /\/embed$/);
});
