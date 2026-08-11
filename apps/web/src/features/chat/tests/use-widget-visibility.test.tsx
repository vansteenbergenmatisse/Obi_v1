import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useWidgetVisibility } from "../ui/use-widget-visibility";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("useWidgetVisibility", () => {
  it("starts closed with no teaser", () => {
    const { result } = renderHook(() => useWidgetVisibility());
    expect(result.current.open).toBe(false);
    expect(result.current.teaser).toBe(false);
  });

  it("shows the teaser 3000ms after mount if still closed", () => {
    const { result } = renderHook(() => useWidgetVisibility());

    act(() => vi.advanceTimersByTime(2999));
    expect(result.current.teaser).toBe(false);

    act(() => vi.advanceTimersByTime(1));
    expect(result.current.teaser).toBe(true);
  });

  it("never shows the initial teaser if the widget is opened first", () => {
    const { result } = renderHook(() => useWidgetVisibility());

    act(() => result.current.openWidget());
    act(() => vi.advanceTimersByTime(3000));

    expect(result.current.teaser).toBe(false);
  });

  it("openWidget opens the panel and hides any visible teaser", () => {
    const { result } = renderHook(() => useWidgetVisibility());
    act(() => vi.advanceTimersByTime(3000));
    expect(result.current.teaser).toBe(true);

    act(() => result.current.openWidget());
    expect(result.current.open).toBe(true);
    expect(result.current.teaser).toBe(false);
  });

  it("closeWidget reschedules the teaser after 20000ms", () => {
    const { result } = renderHook(() => useWidgetVisibility());
    act(() => result.current.openWidget());
    act(() => result.current.closeWidget());
    expect(result.current.open).toBe(false);

    act(() => vi.advanceTimersByTime(19999));
    expect(result.current.teaser).toBe(false);

    act(() => vi.advanceTimersByTime(1));
    expect(result.current.teaser).toBe(true);
  });

  it("dismissTeaser hides it and reschedules after 20000ms, without opening the panel", () => {
    const { result } = renderHook(() => useWidgetVisibility());
    act(() => vi.advanceTimersByTime(3000));
    expect(result.current.teaser).toBe(true);

    act(() => result.current.dismissTeaser());
    expect(result.current.teaser).toBe(false);
    expect(result.current.open).toBe(false);

    act(() => vi.advanceTimersByTime(20000));
    expect(result.current.teaser).toBe(true);
  });
});
