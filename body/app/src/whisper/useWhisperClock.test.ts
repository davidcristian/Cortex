import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { type WhisperFacts, type WhisperRefs, useWhisperClock } from "./useWhisperClock";

/** Take over the frame loop so the test drives time by hand (useMarkClock.test's pattern). */
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

/** A bubble with its text and mist, in the document, letters addable with chosen offsets
 *  (jsdom lays nothing out, so the geometry the clock reads is declared by the test). */
function rig(parented = true) {
  const parent = document.createElement("div");
  const bubble = document.createElement("div");
  const text = document.createElement("span");
  const mist = document.createElement("span");
  bubble.appendChild(text);
  bubble.appendChild(mist);
  if (parented) {
    parent.appendChild(bubble);
    document.body.appendChild(parent);
  } else {
    document.body.appendChild(bubble);
  }
  const refs: WhisperRefs = {
    bubble: { current: bubble },
    text: { current: text },
    mist: { current: mist },
  };
  const lay = (count: number, topOf: (i: number) => number = () => 0): HTMLElement[] => {
    const laid: HTMLElement[] = [];
    for (let i = 0; i < count; i += 1) {
      const ch = document.createElement("span");
      ch.className = "ch";
      Object.defineProperty(ch, "offsetTop", { value: topOf(i) });
      Object.defineProperty(ch, "offsetLeft", { value: 15 + (i % 8) * 7 });
      Object.defineProperty(ch, "offsetWidth", { value: 7 });
      text.appendChild(ch);
      laid.push(ch);
    }
    return laid;
  };
  return { refs, bubble, text, mist, lay };
}

const facts = (over: Partial<WhisperFacts>): WhisperFacts => ({
  streaming: true,
  letters: 0,
  confirmed: 0,
  animated: true,
  onGrow: () => undefined,
  ...over,
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useWhisperClock", () => {
  it("breathes in a posed pill, then talks as the front crosses the first letters", () => {
    const { tick } = fakeFrames();
    const { refs, bubble, lay } = rig();
    const { result, rerender } = renderHook(({ f }) => useWhisperClock(refs, f), {
      initialProps: { f: facts({}) },
    });
    expect(result.current).toBe("breath");
    // The waiting pose is written at mount: the pill drawn around the mist (fallback metrics).
    expect(bubble.style.width).toBe("55px");
    expect(bubble.style.height).toBe("42px");
    tick(0);
    tick(100); // still empty: the loop idles without collecting or advancing
    expect(result.current).toBe("breath");

    const letters = lay(12);
    rerender({ f: facts({ letters: 12, confirmed: 7 }) });
    // One millisecond of travel is not enough front to end the breath yet.
    tick(101);
    expect(result.current).toBe("breath");
    tick(200);
    tick(300);
    tick(400);
    expect(result.current).toBe("talking");
    // The first letter is condensing (fractional opacity and blur, written inline)...
    expect(Number.parseFloat(letters[0]!.style.opacity)).toBeGreaterThan(0);
    expect(letters[0]!.style.filter).toContain("blur");
    // ...while a letter of the held trailing word stays exactly as the class left it.
    expect(letters[11]!.style.opacity).toBe("");
    // A tick with nothing new arrived keeps the collected list (the cheap branch).
    tick(416);
    expect(result.current).toBe("talking");
  });

  it("condenses every letter on the drain, settles, and stops scheduling", () => {
    const { request, tick } = fakeFrames();
    const { refs, bubble, mist, lay } = rig();
    const grew = vi.fn();
    // Two lines: the second's letters sit 40px down, so the box has real height to grow.
    const letters = lay(12, (i) => (i < 6 ? 0 : 40));
    const { result, rerender } = renderHook(({ f }) => useWhisperClock(refs, f), {
      initialProps: { f: facts({ letters: 12, confirmed: 7, onGrow: grew }) },
    });
    let now = 0;
    for (let i = 0; i < 12; i += 1) {
      tick((now += 50));
    }
    expect(result.current).toBe("talking");
    rerender({ f: facts({ letters: 12, confirmed: 7, streaming: false, onGrow: grew }) });
    for (let i = 0; i < 40 && result.current !== "settled"; i += 1) {
      tick((now += 50));
    }
    expect(result.current).toBe("settled");
    for (const ch of letters) {
      expect(ch.style.opacity).toBe("1");
      expect(ch.style.filter).toBe("");
    }
    // The box grew to hold the second line and said so to the tail pin.
    expect(Number.parseFloat(bubble.style.height)).toBeGreaterThan(42);
    expect(grew).toHaveBeenCalled();
    // The mist rode the front as an inline transform, and the loop stopped with the settle.
    expect(mist.style.transform).toContain("translate");
    const scheduled = request.mock.calls.length;
    tick(now + 50);
    expect(request.mock.calls.length).toBe(scheduled);
  });

  it("starts a remounted bubble past its confirmed letters instead of replaying them", () => {
    const { tick } = fakeFrames();
    const { refs, lay } = rig();
    const letters = lay(6);
    const { result } = renderHook(({ f }) => useWhisperClock(refs, f), {
      initialProps: { f: facts({ letters: 6, confirmed: 6 }) },
    });
    tick(0);
    expect(result.current).toBe("talking");
    for (const ch of letters) {
      expect(ch.style.opacity).toBe("1");
    }
  });

  it("settles at once when a turn stops before its first word", () => {
    const { tick } = fakeFrames();
    const { refs } = rig();
    const { result, rerender } = renderHook(({ f }) => useWhisperClock(refs, f), {
      initialProps: { f: facts({}) },
    });
    tick(0);
    rerender({ f: facts({ streaming: false }) });
    tick(50);
    expect(result.current).toBe("settled");
  });

  it("schedules no frames under reduced motion and derives the phase instead", () => {
    const { request } = fakeFrames();
    const { refs } = rig();
    const { result, rerender } = renderHook(({ f }) => useWhisperClock(refs, f), {
      initialProps: { f: facts({ animated: false }) },
    });
    expect(request).not.toHaveBeenCalled();
    expect(result.current).toBe("breath");
    rerender({ f: facts({ animated: false, letters: 3, confirmed: 0 }) });
    expect(result.current).toBe("talking");
    rerender({ f: facts({ animated: false, streaming: false }) });
    expect(result.current).toBe("settled");
  });

  it("does nothing without its elements", () => {
    const { request } = fakeFrames();
    const { refs } = rig();
    const gone = { current: null };
    renderHook(() => useWhisperClock({ ...refs, bubble: gone }, facts({})));
    renderHook(() => useWhisperClock({ ...refs, text: gone }, facts({})));
    renderHook(() => useWhisperClock({ ...refs, mist: gone }, facts({})));
    expect(request).not.toHaveBeenCalled();
  });

  it("poses the pill even without a parent to measure against", () => {
    const { tick } = fakeFrames();
    const { refs, bubble } = rig(false);
    renderHook(() => useWhisperClock(refs, facts({})));
    tick(0);
    expect(bubble.style.width).toBe("55px");
  });

  it("cancels its pending frame when the bubble unmounts", () => {
    const { cancel, tick } = fakeFrames();
    const { refs } = rig();
    const { unmount } = renderHook(() => useWhisperClock(refs, facts({})));
    tick(0);
    unmount();
    expect(cancel).toHaveBeenCalled();
  });
});
