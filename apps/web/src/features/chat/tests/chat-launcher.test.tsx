import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatLauncher } from "../ui/chat-launcher";
import { ChatSessionProvider } from "../ui/chat-session-provider";

afterEach(() => cleanup());

function renderLauncher(props: Parameters<typeof ChatLauncher>[0]) {
  return render(
    <ChatSessionProvider>
      <ChatLauncher {...props} />
    </ChatSessionProvider>,
  );
}

describe("ChatLauncher", () => {
  it("calls onOpen when clicked", async () => {
    const onOpen = vi.fn();
    renderLauncher({ onOpen, pulsing: false });
    await userEvent.click(screen.getByRole("button", { name: "Open assistant" }));
    expect(onOpen).toHaveBeenCalledOnce();
  });

  it("only animates the pulse while a teaser is visible", () => {
    const { rerender } = renderLauncher({ onOpen: vi.fn(), pulsing: false });
    expect(screen.getByRole("button", { name: "Open assistant" }).className).not.toContain(
      "launcher-pulse",
    );

    rerender(
      <ChatSessionProvider>
        <ChatLauncher onOpen={vi.fn()} pulsing />
      </ChatSessionProvider>,
    );
    expect(screen.getByRole("button", { name: "Open assistant" }).className).toContain(
      "launcher-pulse",
    );
  });
});
