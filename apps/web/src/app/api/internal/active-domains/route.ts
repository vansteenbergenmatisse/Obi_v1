/**
 * Internal-only route (PLAN 11.1c, ADR-0014): exposes `activeDomains()` (real `node:fs` read of
 * `config/platforms.json`) over same-origin `fetch` for `middleware.ts`, which runs on the Edge
 * runtime and cannot call `node:fs` directly (see that file's docstring for the full story).
 * Not part of any public contract — never linked, never called by the browser or a platform.
 */
import { NextResponse } from "next/server";
import { activeDomains } from "@/features/embed/platforms";

export function GET(): NextResponse {
  return NextResponse.json({ domains: activeDomains() });
}
