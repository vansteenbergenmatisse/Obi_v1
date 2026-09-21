import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LanguageMenu } from "../ui/language-menu";

afterEach(() => cleanup());

describe("LanguageMenu", () => {
  it("renders all six locales with English checked", () => {
    render(<LanguageMenu open onClose={vi.fn()} activeLocale="en" onSelect={vi.fn()} />);
    expect(screen.getByRole("menuitem", { name: "English" })).toHaveClass("font-semibold");
    for (const label of ["Nederlands", "Deutsch", "Français", "Español", "Italiano"]) {
      expect(screen.getByRole("menuitem", { name: label })).toHaveClass("font-normal");
    }
  });

  it("calls onSelect with the picked locale and closes, without touching the active one", async () => {
    const onClose = vi.fn();
    const onSelect = vi.fn();
    render(<LanguageMenu open onClose={onClose} activeLocale="en" onSelect={onSelect} />);
    await userEvent.click(screen.getByRole("menuitem", { name: "Nederlands" }));
    expect(onSelect).toHaveBeenCalledWith("nl");
    expect(onClose).toHaveBeenCalledOnce();
  });
});
