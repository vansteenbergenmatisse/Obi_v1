import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IconButton } from "../ui/icon-button";

describe("IconButton", () => {
  it("renders its children and fires onClick", async () => {
    const onClick = vi.fn();
    render(
      <IconButton onClick={onClick} aria-label="Close" title="Close">
        X
      </IconButton>,
    );
    const button = screen.getByRole("button", { name: "Close" });
    await userEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("reflects the active prop as aria-pressed", () => {
    render(<IconButton active>M</IconButton>);
    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "true");
  });

  it("does not fire onClick while disabled", async () => {
    const onClick = vi.fn();
    render(
      <IconButton onClick={onClick} disabled>
        M
      </IconButton>,
    );
    await userEvent.click(screen.getByRole("button"));
    expect(onClick).not.toHaveBeenCalled();
  });
});
