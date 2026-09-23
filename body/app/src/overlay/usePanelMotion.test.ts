import { renderHook } from "@testing-library/react";
import { useLayoutEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { lays, resized } from "../test-setup";
import { CEILING_PROPERTY } from "./panelBudget";
import { maxHeight, openHeight } from "./panelGeometry";
import { emptyMemory } from "./panelMemory";
import { place } from "./panelPlacement";
import { usePanelMotion } from "./usePanelMotion";

const VIEWPORT = 1000;

interface Move {
  /** null when the move has no `height` in it at all: a slide of the bottom edge alone. */
  readonly from: { height: number | null; bottom: number };
  readonly to: { height: number | null; bottom: number };
}

/** A stand-in for the browser's geometry animation. */
function harness() {
  const element = document.createElement("div");
  const state = {
    natural: 0,
    displayed: 0,
    /** Where a running slide has got to, when a test wants to interrupt one mid-flight. */
    displayedBottom: null as number | null,
    playState: "running" as AnimationPlayState,
    /** Model what `max-height` does to the panel's `auto` height. */
    capped: false,
  };
  const moves: Move[] = [];
  /** The keyframes exactly as handed to the engine, for the properties `Move` does not model. */
  const keyed: Keyframe[][] = [];
  const played: { onfinish: (() => void) | null; oncancel: (() => void) | null }[] = [];
  const durations: number[] = [];
  const cancels: number[] = [];
  let running = false;
  let animatesHeight = false;

  const live = () => running && state.playState === "running";
  const ceiling = () => Number.parseFloat(element.style.maxHeight || "");
  const height = () => {
    const probing = element.style.getPropertyPriority("height") === "important";
    const own = live() && animatesHeight && !probing ? state.displayed : state.natural;
    return state.capped && !Number.isNaN(ceiling()) ? Math.min(own, ceiling()) : own;
  };
  lays(element, height);
  element.getBoundingClientRect = (() => {
    const offset =
      live() && state.displayedBottom !== null
        ? state.displayedBottom
        : Number.parseFloat(element.style.bottom || "0");
    const bottom = VIEWPORT - offset;
    return { height: height(), bottom, top: bottom - height() } as DOMRect;
  }) as () => DOMRect;

  const parse = (frame: Keyframe) => ({
    height: frame.height === undefined ? null : Number.parseFloat(String(frame.height)),
    bottom: Number.parseFloat(String(frame.bottom ?? "0")),
  });

  element.animate = ((keyframes: Keyframe[], options: KeyframeAnimationOptions) => {
    keyed.push(keyframes);
    moves.push({ from: parse(keyframes[0] ?? {}), to: parse(keyframes[1] ?? {}) });
    durations.push(Math.round(Number(options.duration)));
    animatesHeight = keyframes[0]?.height !== undefined;
    running = true;
    const animation = {
      get playState() {
        return state.playState;
      },
      cancel: () => {
        cancels.push(moves.length);
        running = false;
      },
      onfinish: null as (() => void) | null,
      oncancel: null as (() => void) | null,
    };
    played.push(animation);
    return animation as unknown as Animation;
  }) as typeof element.animate;

  const ref = { current: element };
  const bottom = () => Number.parseFloat(element.style.bottom || "0");
  return { element, ref, state, moves, keyed, durations, cancels, played, bottom };
}

/** How tall a rolling section is right now, which changes under it while the roll runs. */
function rolled(section: HTMLElement, height: number): void {
  lays(section, height);
}

/** A view inside the panel publishing how far short of its tallest shape it currently falls, as
 *  `ConsoleView` does from the two tabs it has measured. */
function slack(parent: HTMLElement, px: number): void {
  const view = document.createElement("div");
  view.className = "view";
  const stack = document.createElement("div");
  stack.setAttribute("data-tab-slack", String(px));
  view.append(stack);
  parent.append(view);
}

/** A section rolling to `target` and `height` tall now, as `Collapse` leaves it in the DOM. */
function rolling(parent: HTMLElement, target: number, height: number): HTMLElement {
  const section = document.createElement("div");
  section.setAttribute("data-morphing", String(target));
  rolled(section, height);
  parent.append(section);
  return section;
}

/** The box a view's content sits in. */
function view(parent: HTMLElement): HTMLElement {
  const box = document.createElement("div");
  box.className = "view";
  parent.append(box);
  return box;
}

/** A section marked `aside` that is not rolling: the reminder stack, present in the panel while
 *  something else moves. */
function staticAside(parent: HTMLElement, height: number): HTMLElement {
  const section = document.createElement("div");
  section.className = "collapse aside";
  rolled(section, height);
  parent.append(section);
  return section;
}

/** A scrolling box inside the panel, subject to the browser's scrollTop clamp. */
function scrollBox(element: HTMLElement, deep: number, measuring: number): HTMLElement {
  const box = document.createElement("div");
  box.className = "history";
  element.append(box);
  let top = 0;
  const clamp = () => {
    const loose = element.style.maxHeight === `${openHeight(VIEWPORT)}px`;
    top = Math.min(top, loose ? measuring : deep);
  };
  Object.defineProperty(box, "scrollTop", {
    configurable: true,
    get: () => {
      clamp();
      return top;
    },
    set: (value: number) => {
      top = value;
      clamp();
    },
  });
  return box;
}

/** A clock the tests can move, because a summon owns the panel's geometry for a fixed window
 *  afterwards. */
function clock(): (ms: number) => void {
  let now = 1_000_000;
  vi.spyOn(Date, "now").mockImplementation(() => now);
  return (ms: number) => {
    now += ms;
  };
}

/** The browser's frame callback, captured so a test can run it by hand: the panel's watch on its
 *  own box is suspended for the frame it writes in and re-attached on the next one. */
function frames() {
  const queue = new Map<number, FrameRequestCallback>();
  let next = 1;
  let cancelled = 0;
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
    queue.set(next, callback);
    return next++;
  });
  vi.spyOn(window, "cancelAnimationFrame").mockImplementation((id) => {
    cancelled += queue.delete(id) ? 1 : 0;
  });
  return {
    run: () => {
      const due = [...queue.values()];
      queue.clear();
      for (const callback of due) {
        callback(0);
      }
    },
    cancelled: () => cancelled,
  };
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
    expect(bottom()).toBe(300);
    expect(ref.current.style.maxHeight).toBe("580px");
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

  it("eases a shrink from the same held edge, so closing a section is not a jump either", () => {
    const { ref, state, moves } = harness();
    state.natural = 520;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 400;
    rerender();
    expect(moves).toEqual([{ from: { height: 520, bottom: 240 }, to: { height: 400, bottom: 240 } }]);
  });

  it("holds the chat's edge through a view change, resizing the console in place", () => {
    const { ref, state, moves, bottom } = harness();
    state.natural = 700;
    const { rerender } = renderHook(({ view }) => usePanelMotion(ref, true, view), {
      initialProps: { view: "chat" },
    });
    expect(bottom()).toBe(150);
    state.natural = 300;
    rerender({ view: "console:shortcuts" });
    expect(bottom()).toBe(150);
    expect(moves).toEqual([{ from: { height: 700, bottom: 150 }, to: { height: 300, bottom: 150 } }]);
  });

  it("slides to true centre on a view change with the recentre switch flipped back on", () => {
    const { element, state, keyed, bottom } = harness();
    const memory = emptyMemory(true, "chat");
    state.natural = 700;
    place(element, memory, { open: true, view: "chat", recentre: false }, true);
    expect(bottom()).toBe(150);
    state.playState = "finished";
    state.natural = 300;
    place(element, memory, { open: true, view: "console:shortcuts", recentre: false }, true);
    expect(bottom()).toBe(350);
    expect(keyed.at(-1)).toEqual([
      { height: "700px", bottom: "150px", maxHeight: "700px" },
      { height: "300px", bottom: "350px", maxHeight: "530px" },
    ]);
    state.playState = "finished";
    state.natural = 700;
    place(element, memory, { open: true, view: "chat", recentre: false }, true);
    expect(bottom()).toBe(150);
  });

  it("enters a multi-shape view at the top its tallest shape would take", () => {
    const { ref, element, state, bottom } = harness();
    state.natural = 700;
    const { rerender } = renderHook(({ view }) => usePanelMotion(ref, true, view), {
      initialProps: { view: "chat" },
    });
    expect(bottom()).toBe(150);
    state.playState = "finished";
    slack(element, 60);
    state.natural = 300;
    rerender({ view: "console" });
    expect(bottom()).toBe(210);
    state.playState = "finished";
    rerender({ view: "console" });
    expect(bottom()).toBe(210);
    state.natural = 700;
    rerender({ view: "chat" });
    expect(bottom()).toBe(150);
  });

  it("holds the console's top edge when a tab resizes it, so the strip stays under the cursor", () => {
    const { ref, state, moves, bottom } = harness();
    state.natural = 700;
    const { rerender } = renderHook(({ view }) => usePanelMotion(ref, true, view), {
      initialProps: { view: "chat" },
    });
    expect(bottom()).toBe(150);
    state.playState = "finished";
    state.natural = 300;
    rerender({ view: "console" });
    expect(bottom()).toBe(150);
    state.playState = "finished";
    state.natural = 420;
    rerender({ view: "console" });
    expect(bottom()).toBe(30);
    expect(moves.at(-1)).toEqual({ from: { height: 300, bottom: 150 }, to: { height: 420, bottom: 30 } });
    state.playState = "finished";
    state.natural = 260;
    rerender({ view: "console" });
    expect(bottom()).toBe(190);
  });

  it("keeps one edge across a console round trip, coming back exactly where it left", () => {
    const { ref, state, moves, bottom } = harness();
    state.natural = 400;
    const { rerender } = renderHook(({ view }) => usePanelMotion(ref, true, view), {
      initialProps: { view: "chat" },
    });
    state.natural = 560;
    rerender({ view: "chat" });
    expect(bottom()).toBe(300);
    state.playState = "finished";
    state.natural = 200;
    rerender({ view: "console:appearance" });
    expect(bottom()).toBe(300);
    state.natural = 560;
    rerender({ view: "chat" });
    expect(bottom()).toBe(300);
    expect(moves[2]).toEqual({ from: { height: 200, bottom: 300 }, to: { height: 560, bottom: 300 } });
  });

  it("gives a first arrival at the chat the edge the console stood on, nothing being parked", () => {
    const { ref, state, bottom } = harness();
    state.natural = 300;
    const { rerender } = renderHook(({ view }) => usePanelMotion(ref, true, view), {
      initialProps: { view: "console:appearance" },
    });
    expect(bottom()).toBe(350);
    state.natural = 500;
    rerender({ view: "chat" });
    expect(bottom()).toBe(350);
  });

  it("caps the height at the ceiling instead of walking the bottom edge down to meet it", () => {
    const { ref, state, bottom } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(300);
    state.natural = 700;
    rerender();
    expect(bottom()).toBe(300);
    expect(ref.current.style.maxHeight).toBe("580px");
    state.natural = 400;
    rerender();
    expect(bottom()).toBe(300);
  });

  it("leaves an aside section out of the height a summon centres on", () => {
    const tick = clock();
    const { ref, element, state, bottom } = harness();
    state.natural = 300;
    const { rerender } = renderHook(({ open }) => usePanelMotion(ref, open, "chat"), {
      initialProps: { open: false },
    });
    rerender({ open: true });
    expect(bottom()).toBe(350);

    tick(1);
    const section = rolling(view(element), 200, 0);
    section.classList.add("collapse", "aside");
    rerender({ open: true });
    expect(bottom()).toBe(350);
  });

  it("counts an arriving aside off the raw height, so the whole panel fits above the edge", () => {
    const tick = clock();
    const { ref, element, state, moves, durations, bottom } = harness();
    state.natural = 400;
    const { rerender } = renderHook(({ open }) => usePanelMotion(ref, open, "chat"), {
      initialProps: { open: false },
    });
    rerender({ open: true });
    expect(bottom()).toBe(300);
    tick(1);
    const section = rolling(view(element), 250, 0);
    section.classList.add("collapse", "aside");
    rerender({ open: true });
    expect(bottom()).toBe(300);
    expect(moves).toEqual([
      { from: { height: 400, bottom: 300 }, to: { height: 580, bottom: 300 } },
    ]);
    expect(durations).toEqual([300]);
  });

  it("counts an aside that is not rolling off an arriving roll's prediction too", () => {
    const tick = clock();
    const { ref, element, state, bottom } = harness();
    const chat = view(element);
    staticAside(chat, 190);
    state.natural = 666;
    const { rerender } = renderHook(({ open }) => usePanelMotion(ref, open, "chat"), {
      initialProps: { open: false },
    });
    rolling(chat, 0, 120);
    rerender({ open: true });
    expect(bottom()).toBe(322);

    tick(1);
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k" }));
    state.natural = 546;
    element.querySelector("[data-morphing]")?.removeAttribute("data-morphing");
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(bottom()).toBe(322);
  });

  it("bounds an arriving roll where the placement bounds it, before the aside comes off", () => {
    const tick = clock();
    const { ref, element, state, moves, bottom } = harness();
    const chat = view(element);
    state.capped = true;
    state.natural = 600;
    const { rerender } = renderHook(({ open }) => usePanelMotion(ref, open, "chat"), {
      initialProps: { open: false },
    });
    rerender({ open: true });
    tick(1);
    const section = rolling(chat, 250, 0);
    section.classList.add("collapse", "aside");
    rerender({ open: true });
    expect(bottom()).toBe(245);
    const slides = moves.length;

    tick(299);
    state.natural = 850;
    section.removeAttribute("data-morphing");
    rolled(section, 250);
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(bottom()).toBe(245);
    expect(moves).toHaveLength(slides);
  });

  it("centres a summon on what it arrives with, not on the height it had while shut", () => {
    const tick = clock();
    const { ref, state, bottom } = harness();
    state.natural = 356;
    const { rerender } = renderHook(({ open }) => usePanelMotion(ref, open, "chat"), {
      initialProps: { open: false },
    });
    rerender({ open: true });
    state.natural = 546;
    rerender({ open: true });
    expect(bottom()).toBe(227);
    tick(500);
    state.natural = 646;
    rerender({ open: true });
    expect(bottom()).toBe(227);
  });

  it("lets a section rolling in behind a summon centre the panel too, in one movement", () => {
    const tick = clock();
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 356;
    const { rerender } = renderHook(({ open }) => usePanelMotion(ref, open, "chat"), {
      initialProps: { open: false },
    });
    rerender({ open: true });
    expect(bottom()).toBe(322);
    rolling(element, 190, 0);
    rerender({ open: true });
    expect(bottom()).toBe(227);
    expect(moves).toEqual([
      { from: { height: null, bottom: 322 }, to: { height: null, bottom: 227 } },
    ]);
    tick(500);
    state.natural = 546;
    element.querySelector("[data-morphing]")?.removeAttribute("data-morphing");
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(bottom()).toBe(227);
    expect(moves).toHaveLength(1);
  });

  it("hands the geometry back to the session the moment the user touches the panel", () => {
    const tick = clock();
    const { ref, state, bottom } = harness();
    state.natural = 356;
    const { rerender } = renderHook(({ open }) => usePanelMotion(ref, open, "chat"), {
      initialProps: { open: false },
    });
    rerender({ open: true });
    expect(bottom()).toBe(322);
    tick(1);
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k" }));
    state.natural = 546;
    rerender({ open: true });
    expect(bottom()).toBe(322);
  });

  it("gives back the exact edge when a section opened inside the arrival window rolls shut", () => {
    const tick = clock();
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 356;
    const { rerender } = renderHook(({ open }) => usePanelMotion(ref, open, "chat"), {
      initialProps: { open: false },
    });
    rerender({ open: true });
    expect(bottom()).toBe(322);

    tick(1);
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k" }));
    const section = rolling(element, 400, 0);
    rerender({ open: true });
    expect(bottom()).toBe(322);
    tick(300);
    state.natural = 756;
    state.playState = "finished";
    section.removeAttribute("data-morphing");
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(bottom()).toBe(322);

    section.setAttribute("data-morphing", "0");
    rolled(section, 400);
    rerender({ open: true });
    expect(bottom()).toBe(322);
    expect(moves).toEqual([]);
  });

  it("does not read the press that summoned the panel as the user touching it", () => {
    const { ref, state, bottom } = harness();
    state.natural = 356;
    const { rerender } = renderHook(({ open }) => usePanelMotion(ref, open, "chat"), {
      initialProps: { open: false },
    });
    window.dispatchEvent(new Event("pointerdown"));
    rerender({ open: true });
    state.natural = 546;
    rerender({ open: true });
    expect(bottom()).toBe(227);
  });

  it("resumes a move the next render did not redirect, rather than restarting its clock", () => {
    const tick = clock();
    const { ref, state, moves, durations } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 422;
    rerender();
    expect(durations).toEqual([120]);

    tick(55);
    state.displayed = 408;
    rerender();
    expect(moves[1]).toEqual({ from: { height: 408, bottom: 300 }, to: { height: 422, bottom: 300 } });
    expect(durations[1]).toBe(65);

    tick(55);
    state.displayed = 419;
    rerender();
    expect(durations[2]).toBe(10);
  });

  it("paces a move afresh once the destination has actually moved", () => {
    const tick = clock();
    const { ref, state, durations } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 422;
    rerender();
    tick(55);
    state.displayed = 408;
    state.natural = 530;
    rerender();
    expect(durations[1]).toBe(193);
  });

  it("predicts a roll no taller than the panel is allowed to be", () => {
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 760;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(120);
    state.playState = "finished";
    rolling(element, 190, 0);
    rerender();
    expect(bottom()).toBe(120);
    expect(moves).toEqual([]);
  });

  it("caps that prediction at the same whole-pixel ceiling the element was given", () => {
    vi.spyOn(window, "innerHeight", "get").mockReturnValue(720);
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 547;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(element.style.maxHeight).toBe("547px");
    expect(bottom()).toBe(86.5);
    state.playState = "finished";
    rolling(element, 76, 0);
    rerender();
    expect(bottom()).toBe(86.5);
    expect(moves).toEqual([]);
  });

  it("takes the ceiling along in the move, on the same edge the panel stands on", () => {
    const { ref, state, keyed } = harness();
    state.natural = 700;
    const { rerender } = renderHook(({ view }) => usePanelMotion(ref, true, view), {
      initialProps: { view: "chat" },
    });
    state.playState = "finished";
    state.natural = 300;
    rerender({ view: "console" });
    expect(keyed.at(-1)).toEqual([
      { height: "700px", bottom: "150px", maxHeight: "730px" },
      { height: "300px", bottom: "150px", maxHeight: "730px" },
    ]);
  });

  it("centres the arriving view on itself, not shy of an aside the leaving view still holds", () => {
    const { element, state, bottom } = harness();
    const chat = document.createElement("div");
    chat.className = "view";
    const aside = document.createElement("div");
    aside.className = "collapse aside";
    lays(aside, 200);
    chat.append(aside);
    element.append(chat);
    const memory = emptyMemory(true, "chat");
    state.natural = 500;
    place(element, memory, { open: true, view: "chat", recentre: false }, true);
    expect(bottom()).toBe(350);

    chat.className = "view out";
    state.playState = "finished";
    state.natural = 300;
    place(element, memory, { open: true, view: "console", recentre: false }, true);
    expect(bottom()).toBe(350);
  });

  it("keeps the real ceiling on the element for the length of a roll, so it cannot overshoot", () => {
    const { ref, element, state } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(element.style.maxHeight).toBe("580px");
    state.playState = "finished";
    rolling(element, 190, 0);
    rerender();
    expect(element.style.maxHeight).toBe("580px");

    rerender();
    expect(element.style.maxHeight).toBe("580px");
  });

  it("ends a roll from the height on screen, not from the one the measuring cap allows", () => {
    const { ref, element, state, moves, bottom } = harness();
    state.capped = true;
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(300);
    state.playState = "finished";

    const section = rolling(element, 190, 0);
    state.natural = 590;
    rerender();
    expect(element.style.maxHeight).toBe("580px");
    expect(moves).toEqual([]);

    section.removeAttribute("data-morphing");
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(moves).toEqual([]);
    expect(bottom()).toBe(300);
  });

  it("hands back a scroll position that its own measurement clamped", () => {
    const { ref, element, state } = harness();
    state.natural = 400;
    const history = scrollBox(element, 400, 80);
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    history.scrollTop = 120;

    state.playState = "finished";
    state.natural = 420;
    rerender();
    expect(history.scrollTop).toBe(120);

    rolling(element, 190, 0);
    rerender();
    expect(history.scrollTop).toBe(120);
  });

  it("scales the duration to the distance moved, between a floor and a ceiling", () => {
    const { ref, state, durations } = harness();
    state.natural = 400;
    const { rerender } = renderHook(({ view }) => usePanelMotion(ref, true, view), {
      initialProps: { view: "chat" },
    });
    state.playState = "finished";
    state.natural = 422;
    rerender({ view: "chat" });
    expect(durations).toEqual([120]);
    state.natural = 552;
    rerender({ view: "chat" });
    expect(durations[1]).toBe(206);
    state.natural = 180;
    rerender({ view: "console:appearance" });
    expect(durations[2]).toBe(380);
  });

  it("publishes every cap it writes, so the sections are budgeted against the panel's own number", () => {
    const { ref, element, state, bottom } = harness();
    state.capped = true;
    state.natural = 300;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(350);
    expect(element.style.maxHeight).toBe("530px");
    expect(element.style.getPropertyValue(CEILING_PROPERTY)).toBe("530px");
    state.playState = "finished";
    const section = rolling(element, 400, 0);
    rerender();
    expect(element.style.getPropertyValue(CEILING_PROPERTY)).toBe(element.style.maxHeight);
    section.remove();
    state.natural = 760;
    rerender();
    expect(element.style.maxHeight).toBe(`${maxHeight(VIEWPORT, bottom())}px`);
    expect(element.style.getPropertyValue(CEILING_PROPERTY)).toBe(element.style.maxHeight);
  });

  it("stops growing at the top rather than reclaiming room by growing downward", () => {
    const { ref, state, bottom } = harness();
    state.natural = 300;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(350);
    state.natural = 760;
    rerender();
    expect(bottom()).toBe(350);
    expect(ref.current.style.maxHeight).toBe("530px");
    expect(VIEWPORT - bottom() - 530).toBe(120);
  });

  it("keeps the panel on screen even if its content somehow outgrows the viewport", () => {
    const { ref, state, bottom } = harness();
    state.natural = 1400;
    renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(0);
  });

  it("cancels the running animation and measures the NATURAL box, not the in-flight one", () => {
    const { ref, state, moves, cancels } = harness();
    state.natural = 300;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 400;
    rerender();
    state.displayed = 360;
    state.natural = 460;
    rerender();
    expect(cancels).toEqual([1]);
    expect(moves[1]).toEqual({ from: { height: 360, bottom: 350 }, to: { height: 460, bottom: 350 } });
  });

  it("animates the change after a finished one, having noticed that it finished", () => {
    const { ref, state, moves } = harness();
    state.natural = 300;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 400;
    rerender();
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

    const section = rolling(element, 0, 60);
    state.natural = 460;
    rerender();
    expect(moves).toEqual([]);

    section.remove();
    state.natural = 400;
    rerender();
    expect(moves).toEqual([]);

    state.natural = 500;
    rerender();
    expect(moves).toEqual([{ from: { height: 400, bottom: 240 }, to: { height: 500, bottom: 240 } }]);
  });

  it("leaves the bottom edge alone through a roll, since growth no longer costs it anything", () => {
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 300;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.playState = "finished";
    state.natural = 600;
    rerender();
    expect(bottom()).toBe(350);

    rolling(element, 100, 0);
    rerender();
    expect(bottom()).toBe(350);
    expect(moves).toHaveLength(1);
  });

  it("has nothing left to move when a roll it followed ends", () => {
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 300;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.playState = "finished";
    state.natural = 600;
    rerender();
    const section = rolling(element, 100, 0);
    rerender();
    expect(bottom()).toBe(350);

    state.natural = 700;
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(moves).toHaveLength(1);

    section.removeAttribute("data-morphing");
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(bottom()).toBe(350);
    expect(moves).toHaveLength(1);
  });

  it("corrects itself when a roll ends somewhere other than where it said it would", () => {
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 300;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.playState = "finished";
    state.natural = 600;
    rerender();
    const section = rolling(element, 100, 0);
    rerender();

    state.natural = 760;
    section.removeAttribute("data-morphing");
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(bottom()).toBe(350);
    expect(moves).toHaveLength(1);
  });

  it("holds the same edge when a roll reverses half way through", () => {
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 300;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.playState = "finished";
    state.natural = 600;
    rerender();
    const section = rolling(element, 100, 0);
    rerender();
    expect(bottom()).toBe(350);

    state.playState = "running";
    state.natural = 650;
    section.setAttribute("data-morphing", "0");
    rolled(section, 50);
    rerender();
    expect(bottom()).toBe(350);
    expect(moves).toHaveLength(1);
  });

  it("carries a height ease that was still in the air through the roll that interrupted it", () => {
    const { ref, element, state, moves, durations, bottom } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(300);
    state.natural = 340;
    rerender();
    expect(moves[0]).toEqual({ from: { height: 400, bottom: 300 }, to: { height: 340, bottom: 300 } });

    state.displayed = 380;
    const section = rolling(element, 100, 0);
    rerender();
    expect(moves[1]).toEqual({ from: { height: 380, bottom: 300 }, to: { height: 440, bottom: 300 } });
    expect(durations[1]).toBe(300);

    state.natural = 470;
    section.removeAttribute("data-morphing");
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(moves[2]).toEqual({ from: { height: 440, bottom: 300 }, to: { height: 470, bottom: 300 } });
    expect(durations[2]).toBe(120);
  });

  it("moves with a roll no render told it about, which is how a reply's trace opens", () => {
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 600;
    renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(200);

    rolling(element, 100, 0);
    element.dispatchEvent(new CustomEvent("cortex:morphstart", { bubbles: true }));
    expect(bottom()).toBe(200);
    expect(moves).toEqual([]);

    state.natural = 700;
    element.querySelector("[data-morphing]")?.removeAttribute("data-morphing");
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(bottom()).toBe(200);
    expect(moves).toHaveLength(0);
  });

  it("places a roll announced mid-commit for the render on screen, not the one before it", () => {
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 500;
    const { rerender } = renderHook(
      ({ open, roll }) => {
        useLayoutEffect(() => {
          if (roll) {
            element.dispatchEvent(new CustomEvent("cortex:morphstart", { bubbles: true }));
          }
        });
        usePanelMotion(ref, open, "chat");
      },
      { initialProps: { open: false, roll: false } },
    );
    expect(bottom()).toBe(250);

    rolling(element, 0, 200);
    rerender({ open: true, roll: true });
    expect(bottom()).toBe(350);
    expect(moves).toEqual([
      { from: { height: null, bottom: 250 }, to: { height: null, bottom: 350 } },
    ]);
  });

  it("stops listening for a section's roll once the panel is gone", () => {
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 300;
    const { unmount } = renderHook(() => usePanelMotion(ref, true, "chat"));
    unmount();
    state.natural = 760;
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(bottom()).toBe(350);
    rolling(element, 100, 0);
    element.dispatchEvent(new CustomEvent("cortex:morphstart", { bubbles: true }));
    expect(bottom()).toBe(350);
    expect(moves).toEqual([]);
  });

  it("marks itself while a move is in the air, so no thumb is drawn for a size it passes through", () => {
    const { ref, element, state, played } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(element.hasAttribute("data-resizing")).toBe(false);
    state.natural = 520;
    rerender();
    expect(element.hasAttribute("data-resizing")).toBe(true);
    played[0]?.onfinish?.();
    expect(element.hasAttribute("data-resizing")).toBe(false);
    state.natural = 600;
    rerender();
    expect(element.hasAttribute("data-resizing")).toBe(true);
    state.playState = "finished";
    rerender();
    expect(element.hasAttribute("data-resizing")).toBe(false);
  });

  it("ignores a change too small to see", () => {
    const { ref, state, moves } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 401;
    rerender();
    expect(moves).toEqual([]);
  });

  it("animates nothing while closed, and does not move the panel it is closing either", () => {
    const { ref, state, moves, bottom } = harness();
    state.natural = 400;
    const { rerender } = renderHook(({ open }) => usePanelMotion(ref, open, "chat"), {
      initialProps: { open: false },
    });
    expect(bottom()).toBe(300);

    state.playState = "finished";
    state.natural = 700;
    rerender({ open: true });
    expect(bottom()).toBe(150);

    state.natural = 400;
    rerender({ open: false });
    expect(bottom()).toBe(150);
    rerender({ open: true });
    expect(bottom()).toBe(300);
    expect(moves).toEqual([]);
  });

  it("eases a resize no render told it about, such as a row released at the end of its exit", () => {
    const { ref, element, state, moves, durations } = harness();
    state.natural = 400;
    renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 452;
    expect(resized(element)).toBe(1);
    expect(moves).toEqual([{ from: { height: 400, bottom: 300 }, to: { height: 452, bottom: 300 } }]);
    expect(durations).toEqual([120]);
  });

  it("leaves the height alone while a section inside is rolling it, frame by frame", () => {
    const tick = clock();
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 356;
    const { rerender } = renderHook(({ open }) => usePanelMotion(ref, open, "chat"), {
      initialProps: { open: false },
    });
    rerender({ open: true });
    expect(bottom()).toBe(322);

    tick(1);
    rolling(element, 190, 0);
    state.natural = 400;
    expect(resized(element)).toBe(1);
    expect(bottom()).toBe(322);
    expect(moves).toEqual([]);
    element.dispatchEvent(new CustomEvent("cortex:morphstart", { bubbles: true }));
    expect(bottom()).toBe(205);
    expect(moves).toHaveLength(1);
  });

  it("leaves its own move in the air rather than retargeting it once a frame", () => {
    const { ref, element, state, moves } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 520;
    rerender();
    expect(moves).toHaveLength(1);
    state.displayed = 460;
    expect(resized(element)).toBe(1);
    expect(moves).toHaveLength(1);

    state.playState = "finished";
    expect(resized(element)).toBe(1);
    expect(moves).toHaveLength(1);
  });

  it("joins the move it is already making when content grows inside it", () => {
    const { ref, element, state, moves, durations } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 520;
    rerender();
    expect(moves).toHaveLength(1);

    state.displayed = 460;
    state.natural = 560;
    expect(resized(element)).toBe(1);
    expect(moves).toEqual([
      { from: { height: 400, bottom: 300 }, to: { height: 520, bottom: 300 } },
      { from: { height: 460, bottom: 300 }, to: { height: 560, bottom: 300 } },
    ]);
    expect(durations.at(-1)).toBe(158);
    expect(element.style.getPropertyValue("height")).toBe("");
    expect(element.style.getPropertyPriority("max-height")).toBe("");
    expect(element.style.maxHeight).toBe("580px");
  });

  it("opens a retarget on the sub-pixel the panel is at, and ends on the edge it wrote", () => {
    const { ref, element, state, keyed, bottom } = harness();
    state.natural = 352.8125;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(323.59375);
    state.natural = 459.28125;
    rerender();

    state.displayed = 459.28125;
    state.natural = 494.28125;
    expect(resized(element)).toBe(1);
    expect(keyed.at(-1)).toEqual([
      { height: "459.28125px", bottom: "323.59375px", maxHeight: "556px" },
      { height: "494.28125px", bottom: "323.59375px", maxHeight: "556px" },
    ]);
    expect(element.style.bottom).toBe("323.59375px");
  });

  it("hears the resize its own placement raised and finds nothing behind it", () => {
    const frame = frames();
    const { ref, element, state, moves } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 520;
    rerender();
    expect(moves).toHaveLength(1);
    frame.run();
    expect(resized(element)).toBe(1);
    expect(moves).toHaveLength(1);
  });

  it("lifts the watch for the frame it writes in, and takes it up again on the next", () => {
    const frame = frames();
    const { ref, element, state, moves } = harness();
    state.natural = 400;
    renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 452;
    expect(resized(element)).toBe(1);
    expect(moves).toHaveLength(1);

    state.playState = "finished";
    state.natural = 500;
    expect(resized(element)).toBe(0);
    expect(moves).toHaveLength(1);

    frame.run();
    expect(resized(element)).toBe(1);
    expect(moves).toHaveLength(2);

    frame.run();
    expect(resized(element)).toBe(1);
    expect(moves).toHaveLength(2);
    expect(resized(element)).toBe(1);
  });

  it("cancels the frame it would have taken the watch up on when the panel goes", () => {
    const frame = frames();
    const { ref, element, state } = harness();
    state.natural = 400;
    const { unmount } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 452;
    expect(resized(element)).toBe(1);
    unmount();
    expect(frame.cancelled()).toBe(1);
    frame.run();
    state.natural = 500;
    expect(resized(element)).toBe(0);
  });

  it("stops watching its own box once the panel is gone", () => {
    const { ref, element, state, moves } = harness();
    state.natural = 400;
    const { unmount } = renderHook(() => usePanelMotion(ref, true, "chat"));
    unmount();
    state.natural = 520;
    expect(resized(element)).toBe(0);
    expect(moves).toEqual([]);
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
