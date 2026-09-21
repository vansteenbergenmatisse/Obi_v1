import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { AssistantMark } from "../ui/assistant-mark";

describe("AssistantMark", () => {
  it("renders as a decorative SVG hidden from assistive tech", () => {
    const { container } = render(<AssistantMark />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute("aria-hidden", "true");
  });

  it("sizes the SVG from the size prop", () => {
    const { container } = render(<AssistantMark size={32} />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("width", "32");
    expect(svg).toHaveAttribute("height", "32");
  });
});
