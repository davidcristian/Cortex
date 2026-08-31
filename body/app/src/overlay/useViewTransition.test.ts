import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useViewTransition } from "./useViewTransition";

const MORPH_MS = 380;

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useViewTransition", () => {
  it("names nothing while the panel is settled on one view", () => {
    const { result } = renderHook(() => useViewTransition("chat", MORPH_MS));
    expect(result.current).toBeNull();
  });

  it("names the outgoing view in the very render the view changes", () => {
    const { result, rerender } = renderHook(({ view }) => useViewTransition(view, MORPH_MS), {
      initialProps: { view: "chat" },
    });
    rerender({ view: "console:appearance" });
    // This render and not one paint later: it is the render that has to lift the chat out of the
    // layout flow, or the chat would define the height the panel is easing away from.
    expect(result.current).toBe("chat");
  });

  it("lets it go once the morph is over", () => {
    const { result, rerender } = renderHook(({ view }) => useViewTransition(view, MORPH_MS), {
      initialProps: { view: "chat" },
    });
    rerender({ view: "console:appearance" });
    act(() => vi.advanceTimersByTime(MORPH_MS));
    expect(result.current).toBeNull();
  });

  it("holds the original view when a second change lands mid-morph", () => {
    const { result, rerender } = renderHook(({ view }) => useViewTransition(view, MORPH_MS), {
      initialProps: { view: "chat" },
    });
    rerender({ view: "console:appearance" });
    act(() => vi.advanceTimersByTime(MORPH_MS / 2));
    // Straight on to a third view: what is still on screen is the chat, so that is what leaves.
    rerender({ view: "console:shortcuts" });
    expect(result.current).toBe("chat");
    act(() => vi.advanceTimersByTime(MORPH_MS));
    expect(result.current).toBeNull();
  });

  it("drops the pending morph when the panel unmounts", () => {
    const { rerender, unmount } = renderHook(({ view }) => useViewTransition(view, MORPH_MS), {
      initialProps: { view: "chat" },
    });
    rerender({ view: "console:appearance" });
    unmount();
    expect(() => vi.advanceTimersByTime(MORPH_MS)).not.toThrow();
  });
});
