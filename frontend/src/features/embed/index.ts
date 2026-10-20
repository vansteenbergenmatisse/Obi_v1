/**
 * embed — public feature root (PLAN 11.1c), the CLIENT-safe entrypoint.
 *
 * `chat`'s client (for the token) and the `/embed` frame's own client component import from
 * here. Deliberately does NOT re-export `platforms.ts` (`node:fs`/`node:path`/`node:url`) even
 * though it lives in this same feature: a barrel that mixes browser-safe code with genuine
 * Node-only built-ins breaks the client webpack bundle the moment ANYTHING imports this file
 * from a `"use client"` module (Next.js resolves the whole barrel's module graph before tree-
 * shaking can remove the unused half) — confirmed by `next build` failing with
 * `UnhandledSchemeError: node:fs` the first time this was tried. Server-only consumers
 * (`middleware.ts`, `app/embed/page.tsx`) import `./platforms` directly instead — see that file's
 * docstring, which also carries `import "server-only"` so a future accidental client import fails
 * loudly at build time rather than repeating this bug.
 */
export { initIframeBridge, getToken } from "./iframe-bridge";
// Edge-safe pure env check (no node:fs) — re-exported so other features read the local/dev signal
// through this root instead of deep-importing `./csp` (substep 8.4.1: the chat standalone-preset
// selector is dev-only). Safe in the client barrel; `platforms.ts` stays out (node:fs) as above.
export { isLocalOrDevEnv } from "./csp";
export type { InitIframeBridgeOptions } from "./iframe-bridge";
export type {
  ObiMessage,
  ObiMessageType,
  ObiOpenMessage,
  ObiTokenMessage,
  ObiClearMessage,
  ObiHiddenMessage,
} from "@omniboost/contracts";
export { OBI_MESSAGE_TYPES, OBI_HIDDEN_MESSAGE_TYPE } from "@omniboost/contracts";
