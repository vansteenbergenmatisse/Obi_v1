import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MenuItem } from "../ui/menu-item";

afterEach(() => cleanup());

describe("MenuItem", () => {
  it("fires onSelect when clicked", async () => {
    const onSelect = vi.fn();
    render(<MenuItem onSelect={onSelect}>Restart conversation</MenuItem>);
    await userEvent.click(screen.getByRole("menuitem", { name: "Restart conversation" }));
    expect(onSelect).toHaveBeenCalledOnce();
  });

  it("is aria-disabled and never fires onSelect when disabled, while staying focusable", async () => {
    const onSelect = vi.fn();
    render(
      <MenuItem onSelect={onSelect} disabled>
        Developer docs
      </MenuItem>,
    );
    const item = screen.getByRole("menuitem", { name: "Developer docs" });
    expect(item).toHaveAttribute("aria-disabled", "true");
    expect(item).not.toHaveAttribute("disabled");
    await userEvent.click(item);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("applies danger styling", () => {
    render(<MenuItem danger>Restart conversation</MenuItem>);
    expect(screen.getByRole("menuitem")).toHaveClass("text-danger");
  });

  it("applies bold weight when active", () => {
    render(<MenuItem active>English</MenuItem>);
    expect(screen.getByRole("menuitem")).toHaveClass("font-semibold");
  });
});
