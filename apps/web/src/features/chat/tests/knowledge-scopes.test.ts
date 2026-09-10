/**
 * Drift guard for the widget's recognized-scope list (PLAN 10.8).
 *
 * The dev scope switcher renders `model/knowledge-scopes.ts`, a hand-mirrored copy of the repo-root
 * `config/knowledge_scopes.json` (Next can't import a JSON from outside the app root into the client
 * bundle). This test reads the CANONICAL file and asserts the two agree, so the widget list can
 * never silently drift from the backend's recognized set — the whole reason the config lives at the
 * repo root (PLAN 10.1) instead of being duplicated.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { KNOWLEDGE_SCOPES } from "../model/knowledge-scopes";

const here = dirname(fileURLToPath(import.meta.url));
// apps/web/src/features/chat/tests → repo root is six directories up.
const canonicalPath = resolve(here, "../../../../../../config/knowledge_scopes.json");

interface CanonicalConfig {
  scopes: { name: string; description: string }[];
}

describe("KNOWLEDGE_SCOPES", () => {
  it("mirrors config/knowledge_scopes.json's scope names in order (no drift)", () => {
    const canonical = JSON.parse(readFileSync(canonicalPath, "utf8")) as CanonicalConfig;
    const canonicalNames = canonical.scopes.map((s) => s.name);
    const widgetNames = KNOWLEDGE_SCOPES.map((s) => s.name);
    expect(widgetNames).toEqual(canonicalNames);
  });

  it("always includes obi-general-test — the always-present base scope (ADR-0011)", () => {
    expect(KNOWLEDGE_SCOPES.map((s) => s.name)).toContain("obi-general-test");
  });
});
