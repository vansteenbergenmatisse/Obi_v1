/**
 * `/test-hosts/*` pages — PLAN 11.1c, ADR-0014. Proves each page wires the correct `tokenUrl` per
 * name and renders the exact paste template a real integrator would copy. `next/script`'s actual
 * script injection/`onLoad` firing is a real-browser concern (jsdom doesn't execute script tags),
 * so live-browser verification is the remaining manual step documented in the hand-back report —
 * this test covers everything the React render itself is responsible for.
 */
import type { ReactElement } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import TestHostsLayout from "./layout";
import { TestHostContent } from "./test-host-content";
import { tokenUrlFor } from "./token-url";

describe("TestHostsLayout", () => {
  it("marks <html> with suppressHydrationWarning to match the sibling root layouts", () => {
    // Guards against the /test-hosts/* hydration mismatch (PLAN 11.1c / NEXT SESSION B):
    // the deliberately-bare host tree is deterministic, so the only legitimate diff is a
    // root-element attribute injected by browser extensions before hydration. Both sibling
    // root layouts ((site) and embed) carry this prop; the test-host one must too.
    // suppressHydrationWarning is a React-only prop (stripped from the DOM), so we assert it
    // on the returned element tree rather than on rendered markup.
    const tree = TestHostsLayout({ children: null }) as ReactElement<{
      suppressHydrationWarning?: boolean;
    }>;
    expect(tree.type).toBe("html");
    expect(tree.props.suppressHydrationWarning).toBe(true);
  });
});

describe("tokenUrlFor", () => {
  it.each(["none", "mews", "toast", "opera-cloud"])("builds the per-name token endpoint for %s", (name) => {
    expect(tokenUrlFor(name)).toBe(`/api/test-hosts/${name}/obi-token`);
  });
});

describe("TestHostContent", () => {
  it.each(["none", "mews", "toast", "opera-cloud"])(
    "renders the heading and paste template with the correct tokenUrl for %s",
    (name) => {
      const tokenUrl = tokenUrlFor(name);
      render(<TestHostContent name={name} tokenUrl={tokenUrl} />);

      expect(screen.getByRole("heading", { name: new RegExp(name) })).toBeInTheDocument();
      const template = screen.getByTestId("paste-template").textContent ?? "";
      expect(template).toContain('src="/obi.js"');
      expect(template).toContain(`Obi.init({ tokenUrl: "${tokenUrl}" });`);
    },
  );
});
