import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { STILL_SECONDS, useMarkClock } from "./useMarkClock";

/** Take over the frame loop so the test drives time by hand. */
function fakeFrames() {
  const callbacks: FrameRequestCallback[] = [];
  let nextId = 0;
  const request = vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
    callbacks.push(callback);
    nextId += 1;
    return nextId;
  });
  const cancel = vi.spyOn(window, "cancelAnimationFrame").mockImplementation(() => undefined);
  const tick = (now: number): void => {
    const next = callbacks.shift();
    act(() => next?.(now));
  };
  return { request, cancel, tick };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useMarkClock", () => {
  it("counts seconds from the first frame, not from the epoch", () => {
    const { tick } = fakeFrames();
    const { result } = renderHook(() => useMarkClock(true));
    expect(result.current).toBe(0);
    // The first frame's timestamp is the origin, so the mark always starts at its pose.
    tick(9000);
    expect(result.current).toBe(0);
    tick(10500);
    expect(result.current).toBe(1.5);
    tick(12000);
    expect(result.current).toBe(3);
  });

  it("schedules no frames at all when the mark is not animated", () => {
    const { request } = fakeFrames();
    const { result } = renderHook(() => useMarkClock(false));
    expect(result.current).toBe(STILL_SECONDS);
    expect(request).not.toHaveBeenCalled();
  });

  it("freezes to the still pose when animation is turned off after running", () => {
    const { tick } = fakeFrames();
    const { result, rerender } = renderHook(({ on }) => useMarkClock(on), {
      initialProps: { on: true },
    });
    tick(1000);
    tick(3000);
    expect(result.current).toBe(2);
    rerender({ on: false });
    expect(result.current).toBe(STILL_SECONDS);
  });

  it("cancels its pending frame when the mark unmounts", () => {
    const { cancel, tick } = fakeFrames();
    const { unmount } = renderHook(() => useMarkClock(true));
    tick(1000);
    unmount();
    expect(cancel).toHaveBeenCalledOnce();
  });
});
