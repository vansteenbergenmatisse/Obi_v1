import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatSessionProvider } from "../ui/chat-session-provider";
import { ChatWidget } from "../ui/chat-widget";

afterEach(() => cleanup());

function renderWidget() {
  return render(
    <ChatSessionProvider>
      <ChatWidget />
    </ChatSessionProvider>,
  );
}

describe("ChatWidget", () => {
  it("renders only the closed launcher initially, no panel", () => {
    renderWidget();
    expect(screen.getByRole("button", { name: "Open assistant" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Chat" })).not.toBeInTheDocument();
  });

  it("opens the panel when the launcher is clicked", async () => {
    renderWidget();
    await userEvent.click(screen.getByRole("button", { name: "Open assistant" }));

    expect(screen.getByRole("region", { name: "Chat" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open assistant" })).not.toBeInTheDocument();
  });

  it("closing the panel (via the header's Close icon) returns to the launcher", async () => {
    renderWidget();
    await userEvent.click(screen.getByRole("button", { name: "Open assistant" }));
    await userEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(screen.queryByRole("region", { name: "Chat" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open assistant" })).toBeInTheDocument();
  });

  describe("teaser timing", () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    it("shows the teaser 3000ms after mount if still closed, and it opens the panel", () => {
      renderWidget();

      act(() => vi.advanceTimersByTime(3000));
      expect(screen.getByText(/Need help with onboarding/)).toBeInTheDocument();

      act(() => screen.getByText(/Need help with onboarding/).click());
      expect(screen.getByRole("region", { name: "Chat" })).toBeInTheDocument();
    });

    it("dismissing the teaser hides it without opening the panel", () => {
      renderWidget();
      act(() => vi.advanceTimersByTime(3000));

      act(() => screen.getByRole("button", { name: "Dismiss" }).click());

      expect(screen.queryByText(/Need help with onboarding/)).not.toBeInTheDocument();
      expect(screen.queryByRole("region", { name: "Chat" })).not.toBeInTheDocument();
    });
  });
});
