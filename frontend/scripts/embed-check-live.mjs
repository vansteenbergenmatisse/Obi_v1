#!/usr/bin/env node
/**
 * embed-check-live.mjs — the live Proof for action-plan substep 8.4.3
 * ("The frontend deploys on Railway"), protecting design panels em-loader + em-hostbackend.
 *
 * Runs the embed checks against a DEPLOYED Obi frontend origin and prints one PASS/FAIL table.
 * It is an operator live-level tool, like backend/scripts/verify_sync_rules.py: it talks to a real
 * network host, so it has no hermetic unit test. Save its output and paste it in the PR (the
 * CLAUDE.md live-level rule).
 *
 * Usage (from repo root or anywhere):
 *   node frontend/scripts/embed-check-live.mjs [origin]
 *   OBI_ORIGIN=https://obi-web-production.up.railway.app node frontend/scripts/embed-check-live.mjs
 * Default origin: https://obi-web-production.up.railway.app (the live obi-web service, 2026-10-09).
 *
 * What it asserts (the substep's three "Must be true" sentences + serving):
 *   1. GET /obi.js  -> 200, and the deployed origin is BAKED into the bundle (not the host-page
 *      fallback) so a real cross-origin host frames ${origin}/embed.
 *   2. GET /embed   -> 200 and carries a content-security-policy with a frame-ancestors directive.
 *   3. frame-ancestors EQUALS the active platforms.json domains (the single source the backend and
 *      this frontend both compute from) — the mechanism, proven against the live header.
 *   4. GET /        -> 200 (the service is up / healthy).
 *
 * Honest scope note (recorded in the ledger as a deviation): the Proof line also wants the embed to
 * PASS "from a test host page on another domain". Today the only active platforms.json entry
 * (obi-test) lists the app's OWN domain, so no EXTERNAL domain is authorized to frame /embed yet —
 * by design, until a real platform domain is registered. That positive external-domain embed is
 * exercised in substep 8.5.3's four-case matrix (single/multiple/unsupported/revoked) once Jasper's
 * Data Hub / Base domains land in platforms.json. This script proves everything achievable before
 * that: serving from the stable origin, the baked origin, and that frame-ancestors is built from
 * the active platform list.
 */

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_ORIGIN = "https://obi-web-production.up.railway.app";
const origin = (process.argv[2] || process.env.OBI_ORIGIN || DEFAULT_ORIGIN).replace(/\/+$/, "");

const here = dirname(fileURLToPath(import.meta.url));
// frontend/scripts -> repo root is two directories up; mirror platforms.ts's resolution.
const platformsPath =
  process.env.PLATFORMS_PATH?.trim() ||
  resolve(here, "../../knowledge-base/config/platforms.json");

/** Sorted, de-duplicated domains of every active:true platform entry — mirrors platforms.ts. */
function expectedActiveDomains() {
  const raw = JSON.parse(readFileSync(platformsPath, "utf8"));
  const domains = new Set();
  for (const entry of Object.values(raw.platforms ?? {})) {
    if (!entry.active) continue;
    for (const d of entry.domains ?? []) domains.add(d);
  }
  return [...domains].sort();
}

/** Parse the frame-ancestors source list out of a CSP header value. */
function frameAncestors(csp) {
  if (!csp) return null;
  const m = csp.split(";").map((s) => s.trim()).find((s) => s.startsWith("frame-ancestors"));
  if (!m) return null;
  return m
    .slice("frame-ancestors".length)
    .trim()
    .split(/\s+/)
    .map((s) => s.replace(/^https?:\/\//, "").replace(/\/+$/, ""))
    .filter(Boolean)
    .sort();
}

const results = [];
const record = (name, pass, detail) => {
  results.push({ name, pass, detail });
  const tag = pass ? "PASS" : "FAIL";
  console.log(`  [${tag}] ${name}${detail ? ` — ${detail}` : ""}`);
};

async function main() {
  console.log(`embed-check-live · target origin: ${origin}`);
  console.log(`platforms.json: ${platformsPath}`);
  console.log(`run at: ${new Date().toISOString()}`);
  console.log("");

  const expected = expectedActiveDomains();
  console.log(`active platforms.json domains (expected frame-ancestors): ${JSON.stringify(expected)}`);
  console.log("");

  // 1. obi.js served + origin baked in
  try {
    const r = await fetch(`${origin}/obi.js`);
    const body = await r.text();
    record("obi.js served (200)", r.status === 200, `status=${r.status}`);
    const baked = body.includes(origin);
    record(
      "deployed origin baked into obi.js (not host-page fallback)",
      baked,
      baked ? `found "${origin}"` : "origin string not present in bundle",
    );
    record(
      "obi.js points its iframe at ${origin}/embed",
      body.includes("/embed"),
      "",
    );
  } catch (e) {
    record("obi.js served (200)", false, String(e));
  }

  // 2 + 3. /embed served + frame-ancestors == active platform domains
  try {
    const r = await fetch(`${origin}/embed`);
    record("/embed served (200)", r.status === 200, `status=${r.status}`);
    const csp = r.headers.get("content-security-policy");
    const fa = frameAncestors(csp);
    record("/embed carries a frame-ancestors CSP", fa !== null, csp ? `csp="${csp}"` : "no CSP header");
    if (fa !== null) {
      const eq = JSON.stringify(fa) === JSON.stringify(expected);
      record(
        "frame-ancestors == active platforms.json domains",
        eq,
        `header=${JSON.stringify(fa)} expected=${JSON.stringify(expected)}`,
      );
    }
  } catch (e) {
    record("/embed served (200)", false, String(e));
  }

  // 4. service up
  try {
    const r = await fetch(`${origin}/`);
    record("service root reachable (200)", r.status === 200, `status=${r.status}`);
  } catch (e) {
    record("service root reachable (200)", false, String(e));
  }

  const failed = results.filter((x) => !x.pass);
  console.log("");
  console.log(`result: ${results.length - failed.length}/${results.length} checks passed`);
  if (failed.length) {
    console.log(`FAILED: ${failed.map((x) => x.name).join("; ")}`);
    process.exit(1);
  }
  console.log("ALL EMBED CHECKS PASSED");
}

main().catch((e) => {
  console.error("embed-check-live crashed:", e);
  process.exit(2);
});
