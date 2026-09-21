import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AttachmentStrip } from "../ui/attachment-strip";

afterEach(() => cleanup());

describe("AttachmentStrip", () => {
  it("renders nothing when there are no attachments", () => {
    const { container } = render(<AttachmentStrip attachments={[]} onRemove={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a thumbnail per attachment and calls onRemove with its id", async () => {
    const onRemove = vi.fn();
    const attachments = [
      { id: "a1", file: new File(["x"], "one.png", { type: "image/png" }), previewUrl: "blob:one" },
      { id: "a2", file: new File(["y"], "two.png", { type: "image/png" }), previewUrl: "blob:two" },
    ];
    render(<AttachmentStrip attachments={attachments} onRemove={onRemove} />);

    expect(screen.getByAltText("one.png")).toBeInTheDocument();
    expect(screen.getByAltText("two.png")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /remove one\.png/i }));

    expect(onRemove).toHaveBeenCalledWith("a1");
  });

  it("opens a full-size lightbox on thumbnail click and closes it on Escape", async () => {
    const attachments = [
      { id: "a1", file: new File(["x"], "one.png", { type: "image/png" }), previewUrl: "blob:one" },
    ];
    render(<AttachmentStrip attachments={attachments} onRemove={vi.fn()} />);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "View one.png" }));

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(screen.getAllByAltText("one.png")).toHaveLength(2); // thumbnail + lightbox

    await userEvent.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes the lightbox via its close button without removing the attachment", async () => {
    const onRemove = vi.fn();
    const attachments = [
      { id: "a1", file: new File(["x"], "one.png", { type: "image/png" }), previewUrl: "blob:one" },
    ];
    render(<AttachmentStrip attachments={attachments} onRemove={onRemove} />);

    await userEvent.click(screen.getByRole("button", { name: "View one.png" }));
    await userEvent.click(screen.getByRole("button", { name: "Close preview" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(onRemove).not.toHaveBeenCalled();
  });
});
