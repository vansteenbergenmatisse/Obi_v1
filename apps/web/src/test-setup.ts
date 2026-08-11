import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

// Explicit cleanup, not `test.globals: true` — this repo's tests import
// describe/it/expect explicitly rather than relying on injected globals.
afterEach(() => {
  cleanup();
});
