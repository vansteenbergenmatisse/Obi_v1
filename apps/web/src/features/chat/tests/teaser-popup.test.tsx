import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TeaserPopup } from "../ui/teaser-popup";

afterEach(() => cleanup());

describe("TeaserPopup", () => {
  it("opens the panel when the card itself is clicked", async () => {
    const onOpen = vi.fn();
    render(<TeaserPopup onOpen={onOpen} onDismiss={vi.fn()} />);
    await userEvent.click(screen.getByText(/Need help with onboarding/));
    expect(onOpen).toHaveBeenCalledOnce();
  });

  it("dismissing never also opens the panel", async () => {
    const onOpen = vi.fn();
    const onDismiss = vi.fn();
    render(<TeaserPopup onOpen={onOpen} onDismiss={onDismiss} />);
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismiss).toHaveBeenCalledOnce();
    expect(onOpen).not.toHaveBeenCalled();
  });
});
