/**
 * Browser test level (substep 0.5.1, CLAUDE.md's test-levels table: `pnpm test:e2e`).
 *
 * One smoke test against `/test-hosts/none` — a real Next.js route, not a hand-built static
 * stub — that already renders exactly the "paste template" a real platform integrator would add
 * (`<script src="/obi.js">` + `Obi.init({ tokenUrl })`), see `src/app/test-hosts/test-host-content.tsx`.
 * `next dev` serves it here; `public/obi.js` is (re)built first (`pnpm run build:obi`, wired into
 * the `test:e2e` script) since it's a gitignored build artifact, not committed.
 */
import { defineConfig, devices } from "@playwright/test";

const PORT = 3100;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
  },
  webServer: {
    command: `pnpm exec next dev --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/test-hosts/none`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
