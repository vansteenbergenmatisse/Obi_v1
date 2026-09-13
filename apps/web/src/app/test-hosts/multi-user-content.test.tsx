/**
 * `/test-hosts/multi` — the multi-user proof page (PLAN §0 NEXT STEP, 2026-09-13). Covers what the
 * React render owns: the user list is exactly the three BUSINESS hosts (never the tokenless
 * `none`), the active user is always shown, and switching (random or explicit) changes who is
 * active. The live `Obi.init` re-point on switch is a real-browser concern (jsdom doesn't run
 * `next/script`), so it's the documented manual step — mirrors `test-host-content.test.tsx`.
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MultiUserContent } from "./multi-user-content";

describe("MultiUserContent", () => {
  it("offers exactly the three business users and never the tokenless 'none' host", () => {
    render(<MultiUserContent />);
    expect(screen.getByRole("button", { name: /Test Hotel/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Test Restaurant/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Test Resort/ })).toBeInTheDocument();
    // `none` carries no business claims, so it must not be a switchable user here.
    expect(screen.queryByRole("button", { name: /general|none/i })).not.toBeInTheDocument();
  });

  it("always shows the currently active user's company and integration", () => {
    render(<MultiUserContent />);
    const active = screen.getByTestId("active-user");
    // Defaults to the first business host: mews / Test Hotel.
    expect(active).toHaveTextContent("Test Hotel");
    expect(active).toHaveTextContent("mews");
  });

  it("switching to a random user changes the active user to a different one", () => {
    render(<MultiUserContent />);
    const before = screen.getByTestId("active-user").textContent ?? "";
    fireEvent.click(screen.getByRole("button", { name: /switch to a random user/i }));
    const after = screen.getByTestId("active-user").textContent ?? "";
    // The picker never re-selects the current user, so a click always visibly changes state.
    expect(after).not.toBe(before);
  });

  it("an explicit per-user button switches the active user to that user", () => {
    render(<MultiUserContent />);
    fireEvent.click(screen.getByRole("button", { name: /Test Resort/ }));
    const active = screen.getByTestId("active-user");
    expect(active).toHaveTextContent("Test Resort");
    expect(active).toHaveTextContent("opera-cloud");
  });
});
