import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
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
