/**
 * Browser tests (substep 1.2.2 — panels ks-deploy / ks-widget / cm-config / w-scope). Prove, in a
 * real Next build, that the widget's dev scope switcher is GENERATED from the one canonical
 * allowlist `knowledge-base/config/knowledge_scopes.json`:
 *   1. the switcher shows exactly the JSON's offerable entries (each `label`, in order);
 *   2. the reserved `classified` scope appears in no DOM node and no outgoing request body;
 *   3. a temp entry added to the JSON shows up after a rebuild (proving the list is generated,
 *      not hand-written).
 *
 * Target: the main site `/`, which mounts `<ChatWidget />` directly (launcher + panel, no
 * cross-origin `/embed` iframe). The `/test-hosts/*` stub host pages CANNOT drive the switcher:
 * it lives inside the `/embed` iframe, whose `obi:open` bridge only accepts messages from an
 * allow-listed embedding origin (`platforms.local.json` lists `localhost:3000/3100`), but
 * Playwright navigates `127.0.0.1:3100` — a different origin — so the panel never opens there.
 * `/` opens the panel with no backend token, which is all these tests need.
 *
 * On test 3: `next dev` DOES watch and recompile the out-of-app-root `@kb` JSON (verified — see the
 * 1.2.2 ledger). The trap is that a single navigation can race the file-watcher's recompile and
 * load a stale bundle, and `toBeVisible` only re-queries the DOM — it never reloads. So this test
 * disables the browser cache (CDP) and RE-NAVIGATES in a retry loop until the rebuilt switcher
 * serves the new label. The canonical JSON is restored in `finally`; `serial` mode keeps tests 1–2
 * from reading the switcher during that window.
 *
 * The switcher is env-gated (`NEXT_PUBLIC_SHOW_SCOPE_SWITCHER`, set for this suite in
 * `playwright.config.ts`); a real embed never renders it. A deterministic jsdom component suite
 * (`src/features/chat/tests/knowledge-scopes.test.tsx`) proves the same facts without a server.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { type Page, expect, test } from "@playwright/test";

test.describe.configure({ mode: "serial" });

const here = dirname(fileURLToPath(import.meta.url));
// frontend/e2e → repo root is two directories up.
const canonicalPath = resolve(here, "../../knowledge-base/config/knowledge_scopes.json");

interface Canonical {
  _readme?: string;
  scopes: { name: string; label: string; description?: string }[];
}
function readCanonical(): Canonical {
  return JSON.parse(readFileSync(canonicalPath, "utf8")) as Canonical;
}

const canonical = readCanonical();
const offerable = canonical.scopes.filter((s) => s.name !== "classified");
const offerableLabels = offerable.map((s) => s.label);
const classifiedLabel = canonical.scopes.find((s) => s.name === "classified")?.label ?? "Classified";

/** Open `/`, open the widget panel, open the scope switcher, and return its menu locator. */
async function openScopeSwitcher(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Open assistant" }).click();
  await expect(page.getByRole("region", { name: "Chat" })).toBeVisible();
  await page.getByRole("button", { name: "Knowledge scope" }).click();
  return page.getByRole("menu", { name: "Knowledge scope" });
}

test("the dev switcher shows exactly the JSON entries, minus classified", async ({ page }) => {
  const menu = await openScopeSwitcher(page);
  await expect(menu.getByRole("menuitem")).toHaveText(offerableLabels);
});

test("classified appears in no DOM node and no request body", async ({ page }) => {
  const bodies: string[] = [];
  // Capture every outgoing chat request body; no live backend needed, so abort once captured.
  await page.route("**/api/chat", async (route) => {
    bodies.push(route.request().postData() ?? "");
    await route.abort();
  });

  const menu = await openScopeSwitcher(page);
  // `classified` (and its label) appears in no menu item — the whole switcher, not just the list.
  await expect(menu.getByText(classifiedLabel, { exact: true })).toHaveCount(0);

  // Pick a real scope and send: the only control that sets `knowledgeScope` cannot set classified,
  // so the outgoing body carries the chosen scope and never the reserved one.
  await menu.getByRole("menuitem", { name: "Toast" }).click();
  await page.getByRole("textbox", { name: "Message" }).fill("hi");
  await page.getByRole("button", { name: "Send" }).click();

  await expect.poll(() => bodies.length).toBeGreaterThan(0);
  const body = JSON.parse(bodies[0]) as { knowledgeScope?: string };
  expect(body.knowledgeScope).toBe("obi-toast-test");
  expect(JSON.stringify(body)).not.toContain("classified");
});

test("a temp entry added to the JSON shows up after a rebuild", async ({ page }) => {
  // Each reload must fetch the freshly recompiled bundle, not a cached chunk.
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });

  const original = readFileSync(canonicalPath, "utf8");
  const mutated = readCanonical();
  // Insert before the reserved `classified` entry so the file stays valid (general + classified
  // both still present).
  mutated.scopes.splice(mutated.scopes.length - 1, 0, {
    name: "obi-tempscope-test",
    label: "Temp Scope",
    description: "temporary — added by scope-list.spec.ts, removed in finally",
  });

  try {
    writeFileSync(canonicalPath, `${JSON.stringify(mutated, null, 2)}\n`);
    // Re-navigate until the rebuilt bundle serves the new label — a single goto can race the
    // recompile, and a stale page never self-corrects (toBeVisible re-queries the DOM, never
    // reloads). No hand edit to the widget: the new entry rides in from the JSON alone.
    await expect(async () => {
      const menu = await openScopeSwitcher(page);
      await expect(menu.getByRole("menuitem", { name: "Temp Scope" })).toBeVisible({
        timeout: 1_000,
      });
    }).toPass({ timeout: 30_000 });
  } finally {
    writeFileSync(canonicalPath, original);
  }
});
