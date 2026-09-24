import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * panel w-proxy · regression for the /embed server-only build break.
 *
 * The chat feature's CLIENT public root (`index.ts`) must never re-export a server-only module.
 * `server/route-handlers.ts` reaches `@/platform/automation-api` → `import "server-only"`, so any
 * `"use client"` module that imports the barrel (e.g. `app/embed/embed-frame.tsx`) drags server-only
 * code into the client bundle and Next fails the build ("You're importing a component that needs
 * server-only ... not supported"), 500-ing `/embed`. Server consumers import `@/features/chat/server`
 * instead — exactly the split `features/embed/index.ts` already documents for its `platforms.ts`.
 */
const CLIENT_ROOT = fileURLToPath(new URL("../index.ts", import.meta.url));

describe("chat client public root", () => {
  it("does not re-export any server-only module from ./server", () => {
    const source = readFileSync(CLIENT_ROOT, "utf8");
    // Any `export ... from "./server..."` (or import) pulls the server-only chain into the client
    // bundle. There must be none on the client root.
    const serverReexport = /\bfrom\s+["']\.\/server(?:\/[^"']*)?["']/;
    expect(source).not.toMatch(serverReexport);
  });
});
