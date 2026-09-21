import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";
import { TypingIndicator } from "../ui/typing-indicator";

function word(): string | null {
  return screen.getByTestId("typing-word").textContent;
}

describe("TypingIndicator", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("renders an initial word from the thinking-word bank with an ellipsis", () => {
    render(<TypingIndicator />);
    expect(word()).toMatch(/…$/);
  });

  it("cycles to a different word every 3800ms", () => {
    render(<TypingIndicator />);
    const first = word();

    act(() => {
      vi.advanceTimersByTime(3800);
    });
    const second = word();

    expect(second).not.toBe(first);
  });

  it("stops cycling once unmounted (no interval leak)", () => {
    const { unmount } = render(<TypingIndicator />);
    unmount();
    expect(() => vi.advanceTimersByTime(20000)).not.toThrow();
  });
});
