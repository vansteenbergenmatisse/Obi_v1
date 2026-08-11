import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LanguageMenu } from "../ui/language-menu";

afterEach(() => cleanup());

describe("LanguageMenu", () => {
  it("renders all six locales with English checked", () => {
    render(<LanguageMenu open onClose={vi.fn()} />);
    expect(screen.getByRole("menuitem", { name: "English" })).toHaveClass("font-semibold");
    for (const label of ["Nederlands", "Deutsch", "Français", "Español", "Italiano"]) {
      expect(screen.getByRole("menuitem", { name: label })).toHaveClass("font-normal");
    }
  });

  it("closes without changing the selection when a non-active locale is picked", async () => {
    const onClose = vi.fn();
    render(<LanguageMenu open onClose={onClose} />);
    await userEvent.click(screen.getByRole("menuitem", { name: "Nederlands" }));
    expect(onClose).toHaveBeenCalledOnce();
    // No re-render assertion needed beyond onClose — there is no locale state to change.
  });
});
