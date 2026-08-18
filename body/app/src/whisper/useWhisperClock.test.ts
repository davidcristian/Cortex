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
 *  (jsdom lays nothing out, so the geometry the clock reads is declared by the test). The log's
 *  own width and the letters' offsets are both settable after the fact, which is how a test says
 *  the window changed size and the paragraph re-wrapped at the new one. */
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
  let logWidth = 0;
  Object.defineProperty(parent, "clientWidth", { get: () => logWidth });
  const refs: WhisperRefs = {
    bubble: { current: bubble },
    text: { current: text },
    mist: { current: mist },
  };
  const spots: { top: number; left: number }[] = [];
  const place = (
    count: number,
    topOf: (i: number) => number,
    leftOf: (i: number) => number,
  ): void => {
    for (let i = 0; i < count; i += 1) {
      spots[i] = { top: topOf(i), left: leftOf(i) };
    }
  };
  const lay = (
    count: number,
    topOf: (i: number) => number = () => 0,
    leftOf: (i: number) => number = (i) => 15 + (i % 8) * 7,
  ): HTMLElement[] => {
    place(count, topOf, leftOf);
    const laid: HTMLElement[] = [];
    for (let i = 0; i < count; i += 1) {
      const ch = document.createElement("span");
      ch.className = "ch";
      Object.defineProperty(ch, "offsetTop", { get: () => spots[i]!.top });
      Object.defineProperty(ch, "offsetLeft", { get: () => spots[i]!.left });
      Object.defineProperty(ch, "offsetWidth", { value: 7 });
      text.appendChild(ch);
      laid.push(ch);
    }
    return laid;
  };
  /** The window changed size: the log is this wide now, and the letters lie here. */
  const resize = (
    width: number,
    topOf: (i: number) => number = () => spots[0]!.top,
    leftOf: (i: number) => number = (i) => spots[i]!.left,
  ): void => {
    logWidth = width;
    place(spots.length, topOf, leftOf);
    window.dispatchEvent(new Event("resize"));
  };
  return { refs, bubble, text, mist, lay, resize };
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
    const rolls: string[] = [];
    bubble.parentElement?.addEventListener("cortex:morphstart", () => rolls.push("start"));
    bubble.parentElement?.addEventListener("cortex:morphend", () => rolls.push("end"));
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
    // The bubble owns its height while it speaks, in the panel's own roll contract: the
    // attribute stands (holding the height being eased to) and the start bubbled up once.
    expect(bubble.getAttribute("data-morphing")).not.toBeNull();
    expect(rolls).toEqual(["start"]);
    rerender({ f: facts({ letters: 12, confirmed: 7, streaming: false, onGrow: grew }) });
    for (let i = 0; i < 60 && result.current !== "settled"; i += 1) {
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
    // The mist rode the front as an inline transform, the roll was handed back with the
    // settle, and the loop stopped.
    expect(mist.style.transform).toContain("translate");
    expect(bubble.hasAttribute("data-morphing")).toBe(false);
    expect(rolls).toEqual(["start", "end"]);
    const scheduled = request.mock.calls.length;
    tick(now + 50);
    expect(request.mock.calls.length).toBe(scheduled);
  });

  it("rolls to the height it stands on, publishing the number its own box carries", () => {
    const { tick } = fakeFrames();
    const { refs, bubble, lay } = rig();
    // The bubble's own metrics, so the target lands where a real one does: `offsetTop` is a whole
    // number in every engine, the line box is not (14.5px at 1.55 is 22.475), so a wrapped line
    // asks for 40 + 22.475 + 10 and no rounding of that agrees with any other.
    bubble.style.paddingTop = "10px";
    bubble.style.paddingLeft = "15px";
    bubble.style.lineHeight = "22.475px";
    lay(12, (i) => (i < 6 ? 0 : 40));
    const { rerender } = renderHook(({ f }) => useWhisperClock(refs, f), {
      initialProps: { f: facts({ letters: 12, confirmed: 7 }) },
    });
    let now = 0;
    let published: string | null = null;
    const run = (frames: number) => {
      for (let i = 0; i < frames; i += 1) {
        tick((now += 50));
        published = bubble.getAttribute("data-morphing") ?? published;
      }
    };
    run(12);
    rerender({ f: facts({ letters: 12, confirmed: 7, streaming: false }) });
    run(60);
    // The panel predicts from this number and its `auto` height then follows the box to the end of
    // the roll: the two are the same height or the prediction is out by the difference.
    expect(published).toBe("72.5");
    expect(bubble.style.height).toBe(`${published}px`);
  });

  it("holds the settle until the mist reaches the last word (the coda)", () => {
    const { tick } = fakeFrames();
    const { refs, lay } = rig();
    // The last letter sits far to the right, so the drain finishes the letters well before
    // the trailing mist can have glided there.
    const letters = lay(8, () => 0, (i) => (i === 7 ? 320 : 15 + i * 7));
    const { result, rerender } = renderHook(({ f }) => useWhisperClock(refs, f), {
      initialProps: { f: facts({ letters: 8, confirmed: 8 }) },
    });
    let now = 0;
    tick((now += 50));
    rerender({ f: facts({ letters: 8, confirmed: 8, streaming: false }) });
    let lettersDoneAt: number | null = null;
    for (let i = 0; i < 60 && result.current !== "settled"; i += 1) {
      tick((now += 50));
      if (lettersDoneAt === null && letters.every((ch) => ch.style.opacity === "1")) {
        lettersDoneAt = i;
        // Every letter is ink, and the reply is still not settled: the mist is en route.
        expect(result.current).toBe("talking");
      }
    }
    expect(lettersDoneAt).not.toBeNull();
    expect(result.current).toBe("settled");
  });

  it("hands the roll back if it unmounts mid-stream", () => {
    const { tick } = fakeFrames();
    const { refs, bubble, lay } = rig();
    const rolls: string[] = [];
    bubble.parentElement?.addEventListener("cortex:morphend", () => rolls.push("end"));
    lay(6);
    const { unmount } = renderHook(() => useWhisperClock(refs, facts({ letters: 6, confirmed: 6 })));
    let now = 0;
    for (let i = 0; i < 3; i += 1) {
      tick((now += 50));
    }
    expect(bubble.hasAttribute("data-morphing")).toBe(true);
    unmount();
    expect(bubble.hasAttribute("data-morphing")).toBe(false);
    expect(rolls).toEqual(["end"]);
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

  it("re-lays the letters at the new wrap width when the window resizes mid-stream", () => {
    const { tick } = fakeFrames();
    const { refs, text, lay, resize } = rig();
    const letters = lay(12);
    renderHook(() => useWhisperClock(refs, facts({ letters: 12, confirmed: 12 })));
    // The wrap the letters were laid at: the log has no width at all, so the cap is the pill.
    expect(text.style.width).toBe("25px");
    let now = 0;
    for (let i = 0; i < 6; i += 1) {
      tick((now += 50));
    }
    expect(letters[0]!.style.opacity).toBe("1");
    resize(1000);
    // The paragraph is re-laid at the width the wider log now offers (82% of it, plus padding,
    // less the padding the text sits inside), and the letters already condensed stay ink: the
    // paint each one carries is its own, not a fact about where it sits.
    expect(text.style.width).toBe("820px");
    expect(letters[0]!.style.opacity).toBe("1");
  });

  it("writes nothing when a resize leaves the wrap width where it was", () => {
    const { tick } = fakeFrames();
    const { refs, text, lay, resize } = rig();
    lay(6);
    renderHook(() => useWhisperClock(refs, facts({ letters: 6, confirmed: 6 })));
    tick(0);
    text.style.width = "1px";
    resize(0);
    expect(text.style.width).toBe("1px");
  });

  it("re-poses a settled bubble on a resize, without starting the loop again", () => {
    const { request, tick } = fakeFrames();
    const { refs, bubble, text, lay, resize } = rig();
    const grew = vi.fn();
    lay(12, (i) => (i < 6 ? 0 : 40));
    const { result, rerender } = renderHook(({ f }) => useWhisperClock(refs, f), {
      initialProps: { f: facts({ letters: 12, confirmed: 12, onGrow: grew }) },
    });
    let now = 0;
    tick((now += 50));
    rerender({ f: facts({ letters: 12, confirmed: 12, streaming: false, onGrow: grew }) });
    for (let i = 0; i < 60 && result.current !== "settled"; i += 1) {
      tick((now += 50));
    }
    expect(result.current).toBe("settled");
    // Two lines' worth of box, standing on the last letter's line.
    expect(bubble.style.height).toBe("72.5px");
    const scheduled = request.mock.calls.length;
    grew.mockClear();
    // A window wide enough to hold the reply on one line: the second line's letters come up
    // beside the first's.
    resize(1000, () => 0, (i) => 15 + i * 7);
    expect(text.style.width).toBe("820px");
    // The box the loop left behind is re-posed from the letters where they lie now, at once and
    // from the same arithmetic the last frame used, so the settled bubble no longer holds a box
    // two lines tall around one line of words.
    expect(bubble.style.width).toBe("142px");
    expect(bubble.style.height).toBe("42px");
    expect(grew).toHaveBeenCalled();
    // And it is a pose, not a restart: nothing was scheduled.
    expect(request.mock.calls.length).toBe(scheduled);
  });

  it("leaves the breath pill alone when a turn that never spoke is resized", () => {
    const { tick } = fakeFrames();
    const { refs, bubble, text, resize } = rig();
    const { result, rerender } = renderHook(({ f }) => useWhisperClock(refs, f), {
      initialProps: { f: facts({}) },
    });
    tick(0);
    rerender({ f: facts({ streaming: false }) });
    tick(50);
    expect(result.current).toBe("settled");
    // A listener that throws is reported to the window rather than to whoever dispatched the
    // event, so the resize would look like it worked from here; this is what makes it a claim
    // about the pose reaching a bubble that has no last letter to pose a box around.
    const raised = vi.fn();
    window.addEventListener("error", raised);
    resize(1000);
    window.removeEventListener("error", raised);
    expect(raised).not.toHaveBeenCalled();
    // The wrap width is still re-laid for whatever the DOM holds, but the pill is padding and
    // the mist, which no window change moves.
    expect(text.style.width).toBe("820px");
    expect(bubble.style.width).toBe("55px");
  });

  it("stops listening for resizes once the bubble unmounts", () => {
    const { tick } = fakeFrames();
    const { refs, text, lay, resize } = rig();
    lay(6);
    const { unmount } = renderHook(() => useWhisperClock(refs, facts({ letters: 6, confirmed: 6 })));
    tick(0);
    unmount();
    resize(1000);
    expect(text.style.width).toBe("25px");
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
