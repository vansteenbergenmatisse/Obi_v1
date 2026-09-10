import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ScopeMenu } from "../ui/scope-menu";

afterEach(() => cleanup());

describe("ScopeMenu", () => {
  it("renders all four recognized scopes with the active one checked", () => {
    render(<ScopeMenu open onClose={vi.fn()} activeScope="obi-mews-test" onSelect={vi.fn()} />);
    expect(screen.getByRole("menuitem", { name: "Mews" })).toHaveClass("font-semibold");
    for (const label of ["General", "Opera Cloud", "Toast"]) {
      expect(screen.getByRole("menuitem", { name: label })).toHaveClass("font-normal");
    }
  });

  it("calls onSelect with the picked scope name and closes", async () => {
    const onClose = vi.fn();
    const onSelect = vi.fn();
    render(<ScopeMenu open onClose={onClose} activeScope="obi-mews-test" onSelect={onSelect} />);
    await userEvent.click(screen.getByRole("menuitem", { name: "Toast" }));
    expect(onSelect).toHaveBeenCalledWith("obi-toast-test");
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("checks nothing when no scope is active (embed default)", () => {
    render(<ScopeMenu open onClose={vi.fn()} activeScope={undefined} onSelect={vi.fn()} />);
    for (const label of ["General", "Mews", "Opera Cloud", "Toast"]) {
      expect(screen.getByRole("menuitem", { name: label })).toHaveClass("font-normal");
    }
  });
});
