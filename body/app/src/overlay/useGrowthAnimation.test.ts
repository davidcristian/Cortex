import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useGrowthAnimation } from "./useGrowthAnimation";

/**
 * A stand-in for the browser's height animation, faithful in the one way that matters: while an
 * animation runs it OVERRIDES the element's measured height, and cancelling restores the natural
 * one. That is what the hook has to work around, so the fake models it rather than just counting
 * calls.
 */
function harness() {
  const element = document.createElement("div");
  const state = { natural: 0, displayed: 0, running: false };
  const started: { from: number; to: number }[] = [];
  const cancels: number[] = [];

  element.getBoundingClientRect = (() =>
    ({ height: state.running ? state.displayed : state.natural }) as DOMRect) as () => DOMRect;

  element.animate = ((keyframes: Keyframe[]) => {
    const from = Number.parseFloat(String(keyframes[0]?.height ?? "0"));
    const to = Number.parseFloat(String(keyframes[1]?.height ?? "0"));
    started.push({ from, to });
    state.running = true;
    const animation = {
      cancel: () => {
        cancels.push(started.length);
        state.running = false;
      },
    };
    return animation as unknown as Animation;
  }) as typeof element.animate;

  const ref = { current: element };
  return { ref, state, started, cancels };
}

function stubMotionPreference(reduce: boolean): void {
  vi.spyOn(window, "matchMedia").mockReturnValue({
    matches: reduce,
    media: "(prefers-reduced-motion: reduce)",
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  } as MediaQueryList);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useGrowthAnimation", () => {
  it("animates nothing on the first measurement, having no previous height to come from", () => {
    const { ref, state, started } = harness();
    state.natural = 400;
    renderHook(() => useGrowthAnimation(ref, true));
    expect(started).toEqual([]);
  });

  it("eases from the old height to the new one when the content resizes", () => {
    const { ref, state, started } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => useGrowthAnimation(ref, true));
    state.natural = 520;
    rerender();
    expect(started).toEqual([{ from: 400, to: 520 }]);
  });

  it("eases a shrink the same way, so closing a section is not a jump either", () => {
    const { ref, state, started } = harness();
    state.natural = 520;
    const { rerender } = renderHook(() => useGrowthAnimation(ref, true));
    state.natural = 400;
    rerender();
    expect(started).toEqual([{ from: 520, to: 400 }]);
  });

  it("cancels the running animation and measures the NATURAL height, not the in-flight one", () => {
    // The regression this hook exists to avoid: a height animation overrides the measured
    // height, so reading it mid-ease returns the in-flight value. Animating from in-flight to
    // in-flight never converges, and during a stream the panel would sit permanently short of
    // its content with the text clipped.
    const { ref, state, started, cancels } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => useGrowthAnimation(ref, true));
    state.natural = 520;
    rerender();
    // Mid-ease: the element measures 450 while the content is really 640 tall.
    state.displayed = 450;
    state.natural = 640;
    rerender();
    expect(cancels).toEqual([1]);
    // From where the eye is (450), to the true content height (640), not to the in-flight one.
    expect(started[1]).toEqual({ from: 450, to: 640 });
  });

  it("ignores a change too small to see", () => {
    const { ref, state, started } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => useGrowthAnimation(ref, true));
    state.natural = 401;
    rerender();
    expect(started).toEqual([]);
  });

  it("animates nothing while the panel is closed, but keeps measuring for the reopen", () => {
    const { ref, state, started } = harness();
    state.natural = 400;
    const { rerender } = renderHook(({ active }) => useGrowthAnimation(ref, active), {
      initialProps: { active: false },
    });
    state.natural = 520;
    rerender({ active: false });
    expect(started).toEqual([]);
    // Reopening at a new size animates from the height measured while closed.
    state.natural = 560;
    rerender({ active: true });
    expect(started).toEqual([{ from: 520, to: 560 }]);
  });

  it("schedules nothing under prefers-reduced-motion", () => {
    stubMotionPreference(true);
    const { ref, state, started } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => useGrowthAnimation(ref, true));
    state.natural = 520;
    rerender();
    expect(started).toEqual([]);
  });

  it("does nothing at all when the element is not mounted", () => {
    const empty = { current: null };
    expect(() => renderHook(() => useGrowthAnimation(empty, true))).not.toThrow();
  });
});
