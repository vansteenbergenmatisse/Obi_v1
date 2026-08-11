import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Menu } from "../ui/menu";

afterEach(() => cleanup());

describe("Menu", () => {
  it("renders nothing when closed", () => {
    render(
      <Menu open={false} onClose={vi.fn()} aria-label="More options">
        <div>item</div>
      </Menu>,
    );
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("renders its children under the given accessible name when open", () => {
    render(
      <Menu open onClose={vi.fn()} aria-label="More options">
        <div>item</div>
      </Menu>,
    );
    expect(screen.getByRole("menu", { name: "More options" })).toBeInTheDocument();
    expect(screen.getByText("item")).toBeInTheDocument();
  });

  it("closes when the outside overlay is clicked", async () => {
    const onClose = vi.fn();
    render(
      <Menu open onClose={onClose} aria-label="More options">
        <div>item</div>
      </Menu>,
    );
    await userEvent.click(screen.getByTestId("menu-overlay"));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
