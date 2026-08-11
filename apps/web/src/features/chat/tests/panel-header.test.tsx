import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PanelHeader } from "../ui/panel-header";
import { ChatSessionProvider } from "../ui/chat-session-provider";

afterEach(() => cleanup());

function renderHeader(props: Parameters<typeof PanelHeader>[0]) {
  return render(
    <ChatSessionProvider>
      <PanelHeader {...props} />
    </ChatSessionProvider>,
  );
}

describe("PanelHeader", () => {
  it("shows the assistant name, defaulting to Obi", () => {
    renderHeader({ onRestart: vi.fn() });
    expect(screen.getByText("Obi")).toBeInTheDocument();
  });

  it("omits the close button when no onClose is given (page variant)", () => {
    renderHeader({ onRestart: vi.fn() });
    expect(screen.queryByRole("button", { name: "Close" })).not.toBeInTheDocument();
  });

  it("shows and wires the close button when onClose is given (widget variant)", async () => {
    const onClose = vi.fn();
    renderHeader({ onRestart: vi.fn(), onClose });
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("opening one menu closes the other (mutually exclusive)", async () => {
    renderHeader({ onRestart: vi.fn() });
    await userEvent.click(screen.getByRole("button", { name: "More" }));
    expect(screen.getByRole("menu", { name: "More options" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Language" }));
    expect(screen.queryByRole("menu", { name: "More options" })).not.toBeInTheDocument();
    expect(screen.getByRole("menu", { name: "Language" })).toBeInTheDocument();
  });

  it("renders docs/support as disabled stubs and wires restart to the real handler", async () => {
    const onRestart = vi.fn();
    renderHeader({ onRestart });
    await userEvent.click(screen.getByRole("button", { name: "More" }));

    expect(screen.getByRole("menuitem", { name: "Developer docs" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    expect(screen.getByRole("menuitem", { name: "Support articles" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );

    await userEvent.click(screen.getByRole("menuitem", { name: "Restart conversation" }));
    expect(onRestart).toHaveBeenCalledOnce();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("closes the open menu on outside click", async () => {
    renderHeader({ onRestart: vi.fn() });
    await userEvent.click(screen.getByRole("button", { name: "More" }));
    expect(screen.getByRole("menu")).toBeInTheDocument();

    await userEvent.click(screen.getByTestId("menu-overlay"));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
