/**
 * Test-only stand-in for the `server-only` package (see `features/embed/platforms.ts`).
 *
 * The real package unconditionally throws — Next.js swaps it for a no-op when building the
 * SERVER webpack graph, and Vitest has no equivalent client/server split, so it needs the same
 * no-op aliased in here (`vitest.config.ts`'s `resolve.alias`) or every test that imports
 * server-only code would fail immediately, even when run from plain Node (never a browser).
 */
export {};
