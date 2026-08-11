import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "node",
    // Pure-logic tests (*.test.ts) stay on the fast node environment; component tests
    // (*.test.tsx) need a DOM, so they alone pay the jsdom cost.
    environmentMatchGlobs: [["src/**/*.test.tsx", "jsdom"]],
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
