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
});
