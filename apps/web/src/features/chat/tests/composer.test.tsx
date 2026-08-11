import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Composer, type ComposerProps } from "../ui/composer";
import { ChatSessionProvider } from "../ui/chat-session-provider";

afterEach(() => cleanup());

function renderComposer(props: ComposerProps) {
  return render(
    <ChatSessionProvider>
      <Composer {...props} />
    </ChatSessionProvider>,
  );
}

describe("Composer", () => {
  it("sends the trimmed message and clears the box on Enter", async () => {
    const onSend = vi.fn();
    renderComposer({ onSend });
    const box = screen.getByRole("textbox", { name: /message/i });

    await userEvent.type(box, "  hello  {Enter}");

    expect(onSend).toHaveBeenCalledWith("hello", []);
    expect(box).toHaveValue("");
  });

  it("inserts a newline on Shift+Enter instead of sending", async () => {
    const onSend = vi.fn();
    renderComposer({ onSend });
    const box = screen.getByRole("textbox", { name: /message/i });

    await userEvent.type(box, "line one");
    await userEvent.type(box, "{Shift>}{Enter}{/Shift}");
    await userEvent.type(box, "line two");

    expect(onSend).not.toHaveBeenCalled();
    expect(box).toHaveValue("line one\nline two");
  });

  it("does not send whitespace-only input", async () => {
    const onSend = vi.fn();
    renderComposer({ onSend });
    const box = screen.getByRole("textbox", { name: /message/i });

    await userEvent.type(box, "   {Enter}");

    expect(onSend).not.toHaveBeenCalled();
  });

  it("sends via the Send button and disables it while empty", async () => {
    const onSend = vi.fn();
    renderComposer({ onSend });
    const box = screen.getByRole("textbox", { name: /message/i });
    const sendButton = screen.getByRole("button", { name: "Send" });

    expect(sendButton).toBeDisabled();

    await userEvent.type(box, "hi");
    expect(sendButton).not.toBeDisabled();

    await userEvent.click(sendButton);
    expect(onSend).toHaveBeenCalledWith("hi", []);
  });

  it("renders the footer disclaimer", () => {
    renderComposer({ onSend: vi.fn() });
    expect(
      screen.getByText("AI may make mistakes. Verify important information."),
    ).toBeInTheDocument();
  });

  it("disables the box, Send, and Attach buttons while a request is pending", () => {
    renderComposer({ onSend: vi.fn(), disabled: true });
    expect(screen.getByRole("textbox", { name: /message/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /attach/i })).toBeDisabled();
  });

  describe("image attachments", () => {
    function pngFile(name = "screenshot.png") {
      return new File(["fake-bytes"], name, { type: "image/png" });
    }

    it("previews an image selected via the file picker and enables Send with no text", async () => {
      const onSend = vi.fn();
      renderComposer({ onSend });
      const sendButton = screen.getByRole("button", { name: "Send" });
      expect(sendButton).toBeDisabled();

      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      await userEvent.upload(fileInput, pngFile());

      expect(screen.getByAltText("screenshot.png")).toBeInTheDocument();
      expect(sendButton).not.toBeDisabled();
    });

    it("previews a pasted image", async () => {
      renderComposer({ onSend: vi.fn() });
      const box = screen.getByRole("textbox", { name: /message/i });
      const file = pngFile("pasted.png");

      fireEvent.paste(box, {
        clipboardData: {
          items: [{ type: "image/png", getAsFile: () => file }],
        },
      });

      expect(screen.getByAltText("pasted.png")).toBeInTheDocument();
    });

    it("removes an attachment via its remove button", async () => {
      renderComposer({ onSend: vi.fn() });
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      await userEvent.upload(fileInput, pngFile());
      expect(screen.getByAltText("screenshot.png")).toBeInTheDocument();

      await userEvent.click(screen.getByRole("button", { name: /remove screenshot\.png/i }));

      expect(screen.queryByAltText("screenshot.png")).not.toBeInTheDocument();
    });

    it("caps attachments at 4 and ignores extras", async () => {
      renderComposer({ onSend: vi.fn() });
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      const files = ["a.png", "b.png", "c.png", "d.png", "e.png"].map((name) => pngFile(name));

      await userEvent.upload(fileInput, files);

      expect(screen.getByAltText("a.png")).toBeInTheDocument();
      expect(screen.getByAltText("d.png")).toBeInTheDocument();
      expect(screen.queryByAltText("e.png")).not.toBeInTheDocument();
    });

    it("shows the PII disclosure while an image is staged, and clears it once removed", async () => {
      renderComposer({ onSend: vi.fn() });
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;

      expect(screen.queryByText(/don.t check images for personal info/i)).not.toBeInTheDocument();

      await userEvent.upload(fileInput, pngFile());
      expect(screen.getByText(/don.t check images for personal info/i)).toBeInTheDocument();

      await userEvent.click(screen.getByRole("button", { name: /remove screenshot\.png/i }));
      expect(screen.queryByText(/don.t check images for personal info/i)).not.toBeInTheDocument();
    });

    it("sends a base64-encoded image attachment with empty text when there is no text", async () => {
      const onSend = vi.fn();
      renderComposer({ onSend });
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      await userEvent.upload(fileInput, pngFile());

      await userEvent.click(screen.getByRole("button", { name: "Send" }));

      await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1));
      expect(onSend).toHaveBeenCalledWith(
        "",
        [
          expect.objectContaining({
            mediaType: "image/png",
            alt: "screenshot.png",
            data: expect.any(String),
          }),
        ],
      );
      const [, images] = onSend.mock.calls[0];
      expect(images[0].data.length).toBeGreaterThan(0);
      expect(images[0].data).not.toMatch(/^data:/);
      // Clearing the composer's own staging state must not revoke the URL handed off to the
      // sent message — the thread still needs it to render the thumbnail.
      expect(screen.queryByAltText("screenshot.png")).not.toBeInTheDocument();
    });

    it("sends both the text and the image attachment when both are present", async () => {
      const onSend = vi.fn();
      renderComposer({ onSend });
      const box = screen.getByRole("textbox", { name: /message/i });
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      await userEvent.upload(fileInput, pngFile());
      await userEvent.type(box, "what is in this image?");

      await userEvent.click(screen.getByRole("button", { name: "Send" }));

      await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1));
      const [text, images] = onSend.mock.calls[0];
      expect(text).toBe("what is in this image?");
      expect(images).toHaveLength(1);
      expect(images[0]).toMatchObject({ mediaType: "image/png", alt: "screenshot.png" });
    });
  });
});
