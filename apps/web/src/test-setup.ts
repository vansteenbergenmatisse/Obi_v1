import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

// Explicit cleanup, not `test.globals: true` — this repo's tests import
// describe/it/expect explicitly rather than relying on injected globals.
afterEach(() => {
  cleanup();
});

// jsdom doesn't implement the Blob URL registry (no-op stubs, not real object URLs) — needed by
// any *.test.tsx exercising the composer's image-attachment previews.
if (typeof URL.createObjectURL !== "function") {
  URL.createObjectURL = () => "blob:mock-url";
}
if (typeof URL.revokeObjectURL !== "function") {
  URL.revokeObjectURL = () => {};
}
