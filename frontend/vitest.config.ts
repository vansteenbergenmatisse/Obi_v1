import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      // Mirror tsconfig's `@kb/*` path alias so the generated scope list (`model/knowledge-scopes.ts`
      // imports `@kb/config/knowledge_scopes.json`) resolves the same repo-root canonical file under
      // Vitest as it does under Next's build (substep 1.2.2).
      "@kb": path.resolve(__dirname, "../knowledge-base"),
      // Next.js swaps the real `server-only` package (which unconditionally throws) for a no-op
      // when building its SERVER webpack graph; Vitest has no such split, so tests need the same
      // no-op here or every test touching `features/embed/platforms.ts` fails on import alone.
      "server-only": path.resolve(__dirname, "./src/test-stubs/server-only.ts"),
    },
  },
  test: {
    environment: "node",
    // Pure-logic tests (*.test.ts) stay on the fast node environment; component tests
    // (*.test.tsx) need a DOM, so they alone pay the jsdom cost.
    environmentMatchGlobs: [["src/**/*.test.tsx", "jsdom"]],
    // jsdom's own default document URL ("about:blank") has no real origin, so
    // `history.replaceState`/`pushState` throw a same-origin SecurityError — needed by
    // access-token.test.tsx, which exercises real URL/history behavior, not a mock.
    environmentOptions: { jsdom: { url: "http://localhost/" } },
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    server: {
      deps: {
        // @omniboost/contracts ships raw TS source (see its package.json `main`); force it
        // through the same transform as first-party source rather than treating it as a
        // prebuilt dependency.
        inline: [/@omniboost\/contracts/],
      },
    },
  },
});
