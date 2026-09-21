/**
 * The widget's recognized-scope list is GENERATED from the ONE canonical allowlist,
 * `knowledge-base/config/knowledge_scopes.json` (substep 1.2.2 — panels ks-deploy / ks-widget /
 * cm-config / w-scope). No hand-written copy, so there is nothing left to drift — the old drift
 * guard (`knowledge-scopes.test.ts`) is deleted.
 *
 * These jsdom component tests are the widget browser/component level (the 18-Sep widget-batch
 * decision: jsdom component tests stand in for per-panel Playwright until Phase 4). A separate
 * `e2e/scope-list.spec.ts` proves the same three facts against the real Next build. Together they
 * prove: the switcher renders exactly the JSON's offerable entries (minus reserved `classified`),
 * in order, showing each entry's `label`; `classified` is never in the DOM and never selectable
 * (so can never ride a request body); and the list FOLLOWS the JSON — a new JSON entry appears
 * with no widget code change.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ScopeMenu } from "../ui/scope-menu";
import { KNOWLEDGE_SCOPES, KNOWLEDGE_SCOPE_NAMES } from "../model/knowledge-scopes";

const here = dirname(fileURLToPath(import.meta.url));
// frontend/src/features/chat/tests → repo root is five directories up (the tag list lives at
// knowledge-base/config, substep 1.1.1); read the SAME canonical file the build generates from.
const canonicalPath = resolve(here, "../../../../../knowledge-base/config/knowledge_scopes.json");

interface CanonicalScope {
  name: string;
  label: string;
  description: string;
}
const canonical = JSON.parse(readFileSync(canonicalPath, "utf8")) as { scopes: CanonicalScope[] };
const offerable = canonical.scopes.filter((s) => s.name !== "classified");

describe("KNOWLEDGE_SCOPES (generated from knowledge_scopes.json)", () => {
  it("is generated from the JSON: every offerable entry, in order, as { name, label }", () => {
    // Not a hand-written array — the exported list is exactly the JSON's scopes minus `classified`,
    // carrying each entry's `name` and human-readable `label` straight through.
    expect(KNOWLEDGE_SCOPES).toEqual(offerable.map((s) => ({ name: s.name, label: s.label })));
  });

  it("always includes obi-general-test — the always-present base scope (ADR-0011)", () => {
    expect(KNOWLEDGE_SCOPE_NAMES).toContain("obi-general-test");
  });
});

describe("ScopeMenu (the dev/verification switcher)", () => {
  it("displays each JSON entry's label, in order, and never the reserved 'classified'", () => {
    render(<ScopeMenu open onClose={() => {}} activeScope={undefined} onSelect={() => {}} />);

    const items = screen.getAllByRole("menuitem");
    expect(items.map((el) => el.textContent)).toEqual(offerable.map((s) => s.label));
    // `classified` (and its label) appears in no menu item — the whole panel, not just the list.
    expect(screen.queryByText("Classified")).toBeNull();
    expect(screen.queryByText("classified")).toBeNull();
  });

  it("never offers 'classified', so it can never be selected into a request body", () => {
    const onSelect = vi.fn();
    render(<ScopeMenu open onClose={() => {}} activeScope={undefined} onSelect={onSelect} />);

    // The switcher is the ONLY control that sets `knowledgeScope`; its options exclude `classified`,
    // so no click can put `classified` on an outgoing request (the ChatSessionProvider tests prove
    // the body carries exactly the scope the switcher set).
    expect(KNOWLEDGE_SCOPE_NAMES).not.toContain("classified");
    const rendered = screen.getAllByRole("menuitem").map((el) => el.textContent);
    expect(rendered).not.toContain("Classified");
  });
});

describe("the list follows the JSON", () => {
  afterEach(() => {
    vi.doUnmock("@kb/config/knowledge_scopes.json");
    vi.resetModules();
  });

  it("a new JSON entry shows up with no widget code change; a new 'classified' entry never does", async () => {
    vi.resetModules();
    vi.doMock("@kb/config/knowledge_scopes.json", () => ({
      default: {
        _readme: "",
        scopes: [
          { name: "obi-general-test", label: "General", description: "" },
          { name: "obi-tempscope-test", label: "Temp Scope", description: "" },
          { name: "classified", label: "Classified", description: "" },
        ],
      },
    }));

    const regenerated = await import("../model/knowledge-scopes");

    // The freshly-added JSON entry is in the list — proof the list is built from the JSON, not a
    // hand-written copy that would need a code edit to follow it.
    expect(regenerated.KNOWLEDGE_SCOPES).toContainEqual({
      name: "obi-tempscope-test",
      label: "Temp Scope",
    });
    // …and `classified` is still filtered out even when freshly present in the JSON.
    expect(regenerated.KNOWLEDGE_SCOPE_NAMES).not.toContain("classified");
  });
});
