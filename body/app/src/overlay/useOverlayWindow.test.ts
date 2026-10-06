import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { OverlayWindow } from "../bridge/types";
import type { Mode } from "./overlayState";
import { WINDOW_HIDE_MS, useOverlayWindow } from "./useOverlayWindow";

function recording(): OverlayWindow & { readonly asked: boolean[] } {
  const asked: boolean[] = [];
  return { asked, setShown: (shown) => asked.push(shown) };
}

describe("useOverlayWindow", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("asks nothing of a window that starts hidden with the overlay", () => {
    const osWindow = recording();
    renderHook(() => useOverlayWindow("hidden", osWindow));
    act(() => vi.advanceTimersByTime(WINDOW_HIDE_MS));
    expect(osWindow.asked).toEqual([]);
  });

  it("shows at once, and hides only once the panel's fade is over", () => {
    const osWindow = recording();
    const { rerender } = renderHook(({ mode }: { mode: Mode }) => useOverlayWindow(mode, osWindow), {
      initialProps: { mode: "panel" as Mode },
    });
    expect(osWindow.asked).toEqual([true]);
    rerender({ mode: "hidden" });
    act(() => vi.advanceTimersByTime(WINDOW_HIDE_MS - 1));
    expect(osWindow.asked).toEqual([true]);
    act(() => vi.advanceTimersByTime(1));
    expect(osWindow.asked).toEqual([true, false]);
  });

  it("asks nothing more while the overlay moves between modes that are on screen", () => {
    const osWindow = recording();
    const { rerender } = renderHook(({ mode }: { mode: Mode }) => useOverlayWindow(mode, osWindow), {
      initialProps: { mode: "panel" as Mode },
    });
    rerender({ mode: "orb" });
    rerender({ mode: "preview" });
    expect(osWindow.asked).toEqual([true]);
  });
});
