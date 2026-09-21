import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TeaserPopup } from "../ui/teaser-popup";
import { ChatSessionProvider } from "../ui/chat-session-provider";

afterEach(() => cleanup());

function renderTeaser(props: Parameters<typeof TeaserPopup>[0]) {
  return render(
    <ChatSessionProvider>
      <TeaserPopup {...props} />
    </ChatSessionProvider>,
  );
}

describe("TeaserPopup", () => {
  it("opens the panel when the card itself is clicked", async () => {
    const onOpen = vi.fn();
    renderTeaser({ onOpen, onDismiss: vi.fn() });
    await userEvent.click(screen.getByText(/Need help with onboarding/));
    expect(onOpen).toHaveBeenCalledOnce();
  });

  it("dismissing never also opens the panel", async () => {
    const onOpen = vi.fn();
    const onDismiss = vi.fn();
    renderTeaser({ onOpen, onDismiss });
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    expect(onDismiss).toHaveBeenCalledOnce();
    expect(onOpen).not.toHaveBeenCalled();
  });

  it("w_launcher_panel_opens_from_either_the_launcher_or_the_teaser", async () => {
    // panel w-launcher: the panel opens from the teaser card as well as the launcher.
    const onOpen = vi.fn();
    renderTeaser({ onOpen, onDismiss: vi.fn() });
    await userEvent.click(screen.getByText(/Need help with onboarding/));
    expect(onOpen).toHaveBeenCalledOnce();
  });
});
