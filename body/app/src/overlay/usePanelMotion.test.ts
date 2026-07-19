import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { usePanelMotion } from "./usePanelMotion";

const VIEWPORT = 1000;

interface Move {
  readonly from: { height: number; bottom: number };
  readonly to: { height: number; bottom: number };
}

/**
 * A stand-in for the browser's geometry animation, faithful in the two ways that matter: while an
 * animation runs it OVERRIDES the element's measured box, and a FINISHED animation stops
 * overriding it while still being the last animation the hook holds. The second is what the first
 * version of this hook got wrong: it treated any non-null animation as live, read the finished
 * one's measurement as "what is displayed", and so animated only every other size change. Measured
 * in a browser: opening the chat switcher jumped, closing it eased, opening it jumped.
 */
function harness() {
  const element = document.createElement("div");
  const state = { natural: 0, displayed: 0, playState: "running" as AnimationPlayState };
  const moves: Move[] = [];
  const cancels: number[] = [];
  let running = false;

  element.getBoundingClientRect = (() => {
    const height = running ? state.displayed : state.natural;
    // The element sits at whatever `bottom` the hook last wrote, expressed as a viewport rect.
    const bottom = VIEWPORT - Number.parseFloat(element.style.bottom || "0");
    return { height, bottom, top: bottom - height } as DOMRect;
  }) as () => DOMRect;

  const parse = (frame: Keyframe) => ({
    height: Number.parseFloat(String(frame.height ?? "0")),
    bottom: Number.parseFloat(String(frame.bottom ?? "0")),
  });

  element.animate = ((keyframes: Keyframe[]) => {
    moves.push({ from: parse(keyframes[0] ?? {}), to: parse(keyframes[1] ?? {}) });
    running = true;
    return {
      get playState() {
        return state.playState;
      },
      cancel: () => {
        cancels.push(moves.length);
        running = false;
      },
    } as unknown as Animation;
  }) as typeof element.animate;

  const ref = { current: element };
  const bottom = () => Number.parseFloat(element.style.bottom || "0");
  return { element, ref, state, moves, cancels, bottom };
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

vi.spyOn(window, "innerHeight", "get").mockReturnValue(VIEWPORT);

afterEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(window, "innerHeight", "get").mockReturnValue(VIEWPORT);
});

describe("usePanelMotion", () => {
  it("centres the panel for its height and caps it at three quarters of the viewport", () => {
    const { ref, state, moves, bottom } = harness();
    state.natural = 400;
    renderHook(() => usePanelMotion(ref, true, "chat"));
    // (1000 - 400) / 2: as much clear space below as above.
    expect(bottom()).toBe(300);
    expect(ref.current.style.maxHeight).toBe("760px");
    // Nothing to animate from on the first measurement.
    expect(moves).toEqual([]);
  });

  it("grows upward inside a view: the bottom edge stays where the composer was left", () => {
    const { ref, state, moves, bottom } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 520;
    rerender();
    expect(bottom()).toBe(300);
    expect(moves).toEqual([{ from: { height: 400, bottom: 300 }, to: { height: 520, bottom: 300 } }]);
  });

  it("eases a shrink from the same pinned edge, so closing a section is not a jump either", () => {
    const { ref, state, moves } = harness();
    state.natural = 520;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 400;
    rerender();
    expect(moves).toEqual([{ from: { height: 520, bottom: 240 }, to: { height: 400, bottom: 240 } }]);
  });

  it("re-centres on a view change, sliding and resizing in one movement", () => {
    const { ref, state, moves, bottom } = harness();
    state.natural = 700;
    const { rerender } = renderHook(({ view }) => usePanelMotion(ref, true, view), {
      initialProps: { view: "chat" },
    });
    expect(bottom()).toBe(150);
    // The shortcuts view is much shorter: the panel shrinks to it AND returns to true centre.
    state.natural = 300;
    rerender({ view: "shortcuts" });
    expect(bottom()).toBe(350);
    expect(moves).toEqual([{ from: { height: 700, bottom: 150 }, to: { height: 300, bottom: 350 } }]);
  });

  it("stops growing upward at the ceiling, ending centred rather than jammed at the top", () => {
    const { ref, state, bottom } = harness();
    // A short panel, centred low enough that growing to full height would run off the top.
    state.natural = 300;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(350);
    state.natural = 760;
    rerender();
    // 12% of the viewport is kept clear above, which for a full-height panel is dead centre.
    expect(bottom()).toBe(120);
    expect(VIEWPORT - bottom() - 760).toBe(120);
  });

  it("keeps the panel on screen even if its content somehow outgrows the viewport", () => {
    const { ref, state, bottom } = harness();
    state.natural = 1400;
    renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(0);
  });

  it("cancels the running animation and measures the NATURAL box, not the in-flight one", () => {
    // The regression this hook exists to avoid: a height animation overrides the measured height,
    // so reading it mid-ease returns the in-flight value. Animating from in-flight to in-flight
    // never converges, and during a stream the panel would sit permanently short of its content
    // with the text clipped.
    const { ref, state, moves, cancels } = harness();
    state.natural = 300;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 400;
    rerender();
    // Mid-ease: the element measures 360 while the content is really 460 tall.
    state.displayed = 360;
    state.natural = 460;
    rerender();
    expect(cancels).toEqual([1]);
    // From where the eye is (360), to the true content height, not to the in-flight one.
    expect(moves[1]).toEqual({ from: { height: 360, bottom: 350 }, to: { height: 460, bottom: 350 } });
  });

  it("animates the change after a finished one, having noticed that it finished", () => {
    const { ref, state, moves } = harness();
    state.natural = 300;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 400;
    rerender();
    // The first ease completes; the element is back to reporting its natural box.
    state.playState = "finished";
    state.natural = 460;
    rerender();
    expect(moves).toHaveLength(2);
    expect(moves[1]).toEqual({ from: { height: 400, bottom: 350 }, to: { height: 460, bottom: 350 } });
  });

  it("stands down while a section inside is collapsing, and does not replay it afterwards", () => {
    const { ref, element, state, moves } = harness();
    state.natural = 520;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));

    // A section starts rolling shut. It animates its own height and the panel's `auto` height
    // follows frame by frame, so the panel must not animate the same pixels against it.
    const section = document.createElement("div");
    section.setAttribute("data-morphing", "");
    element.append(section);
    state.natural = 460;
    rerender();
    expect(moves).toEqual([]);

    // The roll finishes and the section unmounts, which re-renders the panel. The move is over
    // and already on screen: easing "from" the mid-roll height would snap it back open.
    section.remove();
    state.natural = 400;
    rerender();
    expect(moves).toEqual([]);

    // The next ordinary change animates again, from where the collapse left the panel.
    state.natural = 500;
    rerender();
    expect(moves).toEqual([{ from: { height: 400, bottom: 240 }, to: { height: 500, bottom: 240 } }]);
  });

  it("re-measures when a section says it has stopped rolling, and slides off the ceiling", () => {
    // A section rolling OPEN finishes without changing any state, so no render follows it. The
    // panel would otherwise never learn it had grown, and a switcher opened on a tall chat sat
    // 39px from the top of the screen with 177px of space below it.
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 300;
    renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(350);

    const section = document.createElement("div");
    section.setAttribute("data-morphing", "");
    element.append(section);
    state.natural = 760;
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    // Still rolling: the section owns the height, and the panel keeps its hands off.
    expect(bottom()).toBe(350);

    section.remove();
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(bottom()).toBe(120);
    // The height is already on screen, so only the slide off the ceiling is animated.
    expect(moves).toEqual([{ from: { height: 760, bottom: 350 }, to: { height: 760, bottom: 120 } }]);
  });

  it("stops listening for a section's roll once the panel is gone", () => {
    const { ref, element, state, bottom } = harness();
    state.natural = 300;
    const { unmount } = renderHook(() => usePanelMotion(ref, true, "chat"));
    unmount();
    state.natural = 760;
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(bottom()).toBe(350);
  });

  it("ignores a change too small to see", () => {
    const { ref, state, moves } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 401;
    rerender();
    expect(moves).toEqual([]);
  });

  it("animates nothing while closed, but keeps measuring so a reopen comes back centred", () => {
    const { ref, state, moves, bottom } = harness();
    state.natural = 400;
    const { rerender } = renderHook(({ open }) => usePanelMotion(ref, open, "chat"), {
      initialProps: { open: false },
    });
    state.natural = 700;
    rerender({ open: false });
    expect(moves).toEqual([]);
    // A dismissed panel comes back to the middle, not to wherever the last chat pushed it.
    expect(bottom()).toBe(150);
  });

  it("re-centres when the window itself is resized", () => {
    const { ref, state, bottom } = harness();
    state.natural = 400;
    renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(300);
    vi.spyOn(window, "innerHeight", "get").mockReturnValue(600);
    window.dispatchEvent(new Event("resize"));
    expect(bottom()).toBe(100);
  });

  it("stops listening for resizes once the panel is gone", () => {
    const { ref, state, bottom } = harness();
    state.natural = 400;
    const { unmount } = renderHook(() => usePanelMotion(ref, true, "chat"));
    unmount();
    vi.spyOn(window, "innerHeight", "get").mockReturnValue(600);
    window.dispatchEvent(new Event("resize"));
    expect(bottom()).toBe(300);
  });

  it("schedules nothing under prefers-reduced-motion, but still places the panel", () => {
    stubMotionPreference(true);
    const { ref, state, moves, bottom } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 520;
    rerender();
    expect(moves).toEqual([]);
    expect(bottom()).toBe(300);
  });

  it("does nothing at all when the element is not mounted", () => {
    const empty = { current: null };
    expect(() => renderHook(() => usePanelMotion(empty, true, "chat"))).not.toThrow();
  });
});
