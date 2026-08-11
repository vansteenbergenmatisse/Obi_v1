import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatLauncher } from "../ui/chat-launcher";

afterEach(() => cleanup());

describe("ChatLauncher", () => {
  it("calls onOpen when clicked", async () => {
    const onOpen = vi.fn();
    render(<ChatLauncher onOpen={onOpen} pulsing={false} />);
    await userEvent.click(screen.getByRole("button", { name: "Open assistant" }));
    expect(onOpen).toHaveBeenCalledOnce();
  });

  it("only animates the pulse while a teaser is visible", () => {
    const { rerender } = render(<ChatLauncher onOpen={vi.fn()} pulsing={false} />);
    expect(screen.getByRole("button", { name: "Open assistant" }).className).not.toContain(
      "launcher-pulse",
    );

    rerender(<ChatLauncher onOpen={vi.fn()} pulsing />);
    expect(screen.getByRole("button", { name: "Open assistant" }).className).toContain(
      "launcher-pulse",
    );
  });
});
