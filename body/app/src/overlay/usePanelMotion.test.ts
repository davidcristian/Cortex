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

/**
 * A stand-in for the browser's geometry animation. It reproduces two behaviours the hook depends
 * on: a running animation overrides the properties it animates and nothing else, and a finished
 * animation stops overriding them while still being the last animation the hook holds. The first
 * version of the hook treated any non-null animation as live and read the finished one's
 * measurement as the displayed height, so it animated only every other size change. Measured in a
 * browser: opening the chat switcher jumped, closing it eased, opening it jumped.
 */
function harness() {
  const element = document.createElement("div");
  const state = {
    natural: 0,
    displayed: 0,
    /** Where a running slide has got to, when a test wants to interrupt one mid-flight. */
    displayedBottom: null as number | null,
    playState: "running" as AnimationPlayState,
    /** Model what `max-height` does to the panel's `auto` height. Off by default, because most of
     *  these tests are about the arithmetic and want to state a height and get it back; on for the
     *  defects that live in the gap between the height a cap allows and the height the panel is
     *  actually standing at. */
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

  // Only a running animation overrides the box: one that has finished without a fill leaves the
  // element to its own layout, even though the hook still holds a reference to it.
  const live = () => running && state.playState === "running";
  const ceiling = () => Number.parseFloat(element.style.maxHeight || "");
  const height = () => {
    // The natural-height probe returns the box to layout for the length of one read by declaring
    // `height: auto` important, which outranks the animation origin. While it is set, the answer is
    // the panel's own layout even though the animation is still running.
    const probing = element.style.getPropertyPriority("height") === "important";
    const own = live() && animatesHeight && !probing ? state.displayed : state.natural;
    return state.capped && !Number.isNaN(ceiling()) ? Math.min(own, ceiling()) : own;
  };
  // The hook reads the height off the computed style and only the bottom edge off the rect, because
  // the rect is measured after the panel's summon transform and the used height is not.
  lays(element, height);
  element.getBoundingClientRect = (() => {
    // The element sits at whatever `bottom` the hook last wrote, expressed as a viewport rect,
    // unless a slide is running and the test has said where it has got to.
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

/** A section rolling to `target` and `height` tall right now, as `Collapse` leaves it in the DOM. */
function rolling(parent: HTMLElement, target: number, height: number): HTMLElement {
  const section = document.createElement("div");
  section.setAttribute("data-morphing", String(target));
  rolled(section, height);
  parent.append(section);
  return section;
}

/** The box a view's content sits in. The aside rule is written against the view being placed, so a
 *  section outside a view box is not an aside of anything. */
function view(parent: HTMLElement): HTMLElement {
  const box = document.createElement("div");
  box.className = "view";
  parent.append(box);
  return box;
}

/** A section marked `aside` that is not rolling: the reminder stack, present in the panel while
 *  something else moves. */
function standing(parent: HTMLElement, height: number): HTMLElement {
  const section = document.createElement("div");
  section.className = "collapse aside";
  rolled(section, height);
  parent.append(section);
  return section;
}

/**
 * A scrolling box inside the panel, subject to the browser's scrollTop clamp.
 *
 * The panel measures itself under the loosest cap any edge could allow, so for that read it is
 * taller and every box inside it is taller too. The engine clamps a box's scrollTop to the range it
 * has at that moment, and putting the real cap back does not restore the old value: `deep` is the
 * range the box has at rest, and `measuring` the shorter range it has while the panel is being
 * measured.
 */
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

/**
 * A clock the tests can move, because a summon owns the panel's geometry for a fixed window
 * afterwards. Without it every step of a test happens inside the same millisecond, which is what a
 * summon and the content landing behind it actually look like.
 */
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
    // (1000 - 400) / 2: as much clear space below as above.
    expect(bottom()).toBe(300);
    // Everything between the edge it sits on and the clear space kept at the top: 880 - 300.
    expect(ref.current.style.maxHeight).toBe("580px");
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

  it("holds the chat's edge through a view change, resizing the console in place", () => {
    const { ref, state, moves, bottom } = harness();
    state.natural = 700;
    const { rerender } = renderHook(({ view }) => usePanelMotion(ref, true, view), {
      initialProps: { view: "chat" },
    });
    expect(bottom()).toBe(150);
    // The console is much shorter and takes its height from the edge the chat stood on. The
    // maintainer chose that edge over a slide to true centre (2026-07-21); the slide stays one flip
    // of `VIEW_CHANGE_RECENTRES` away and is held green by the flipped-switch tests below.
    state.natural = 300;
    rerender({ view: "console:shortcuts" });
    expect(bottom()).toBe(150);
    expect(moves).toEqual([{ from: { height: 700, bottom: 150 }, to: { height: 300, bottom: 150 } }]);
  });

  it("slides to true centre on a view change with the recentre switch flipped back on", () => {
    // The behaviour kept one flip away: entering another view resizes the panel and slides it to
    // the middle of the screen, and the way back restores the chat's parked edge rather than
    // centring a second time. Driven through `place` directly, because the hook always places at
    // the constant's own setting.
    const { element, state, keyed, bottom } = harness();
    const memory = emptyMemory(true, "chat");
    state.natural = 700;
    place(element, memory, { open: true, view: "chat", recentre: false }, true);
    expect(bottom()).toBe(150);
    state.playState = "finished";
    state.natural = 300;
    place(element, memory, { open: true, view: "console:shortcuts", recentre: false }, true);
    expect(bottom()).toBe(350);
    // The ceiling belongs to where the panel is going (880 less 350) and is on the element
    // already, so the move's first frame starts the cap where the panel actually stands: at 700,
    // not clamped flat to 530.
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
    // The console's two tabs are different heights, so entering on the shorter one put its strip
    // lower down the screen than entering on the taller one did. The view publishes how far short
    // it falls and the panel adds that to its bottom edge, which fixes the top at one height
    // whichever tab it is opened on.
    const { ref, element, state, bottom } = harness();
    state.natural = 700;
    const { rerender } = renderHook(({ view }) => usePanelMotion(ref, true, view), {
      initialProps: { view: "chat" },
    });
    expect(bottom()).toBe(150);
    state.playState = "finished";
    // Into the console on its shorter tab: 300 tall, 60 short of the tallest. It sits on the
    // chat's 150 plus that 60, which puts its top at 1000 - 210 - 300 = 490, where the 360px tall
    // tab would have started from the same edge.
    slack(element, 60);
    state.natural = 300;
    rerender({ view: "console" });
    expect(bottom()).toBe(210);
    // A second placement in the same view must not spend the slack again.
    state.playState = "finished";
    rerender({ view: "console" });
    expect(bottom()).toBe(210);
    // Back to the chat, which is one shape and takes its own parked edge whether or not slack is
    // published.
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
    // Entering sits on the edge the chat was on, because the opener that was clicked is in the hint
    // strip at the bottom. The panel's top is now at 1000 - 150 - 300 = 550.
    state.natural = 300;
    rerender({ view: "console" });
    expect(bottom()).toBe(150);
    // A tab change is the same view resizing, and the strip that was clicked is at the top, so the
    // top edge holds: 550 stays, and the bottom moves to 1000 - 550 - 420 = 30.
    state.playState = "finished";
    state.natural = 420;
    rerender({ view: "console" });
    expect(bottom()).toBe(30);
    expect(moves.at(-1)).toEqual({ from: { height: 300, bottom: 150 }, to: { height: 420, bottom: 30 } });
    // And back the other way, the top still held: 1000 - 550 - 260 = 190.
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
    // The conversation grows, pinned to the edge the composer was left at.
    state.natural = 560;
    rerender({ view: "chat" });
    expect(bottom()).toBe(300);
    // Each move settles before the next begins, so every step eases from the last one's end.
    state.playState = "finished";
    // The console resizes on that same edge, and the chat comes back to it. The parked edge gives
    // the same return even if the way out had moved, so the restore stays correct the moment the
    // slide is switched back on.
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
    // The session opened on the console, so no chat edge was ever parked: the chat takes the edge
    // on screen, the same rule as every other view change.
    state.natural = 500;
    rerender({ view: "chat" });
    expect(bottom()).toBe(350);
  });

  it("caps the height at the ceiling instead of walking the bottom edge down to meet it", () => {
    const { ref, state, bottom } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(300);
    // A section rolls open and the panel needs more room than there is above it. All growth is
    // upward: the edge the composer sits on does not move, and the panel stops getting taller at
    // 880 - 300, which puts its top edge on the 12% line.
    state.natural = 700;
    rerender();
    expect(bottom()).toBe(300);
    expect(ref.current.style.maxHeight).toBe("580px");
    // Closing it again leaves the edge where it was, so the panel returns to its starting geometry.
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

    // The reminder stack rolls in behind the summon, taking the panel to 500. The stack can be two
    // rows or five, so the panel centres on the 300 the chat takes and the stack grows it upward
    // from there. Centring on 500 instead placed the conversation according to the day's reminder
    // count, measured 26px below its own centre.
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
    // The stack rolling in behind this summon needs more than the ceiling above that edge allows:
    // 400 of chat plus 250 of reminders against the 580 the edge affords. Centring the chat on the
    // clamped prediction pinned an edge the whole panel could not fit above, the cap written for it
    // squeezed the chat under the rolling stack, and the placement after the roll undid it, which
    // is a second movement on every summon whose reminders outgrow the ceiling. Reported by the
    // user at a 760px viewport: the history lost 119px over the roll and got 40 back afterwards.
    // Counted off the raw height, the chat's own 400 centres and the edge stays where the summon
    // put it.
    tick(1);
    const section = rolling(view(element), 250, 0);
    section.classList.add("collapse", "aside");
    rerender({ open: true });
    expect(bottom()).toBe(300);
    // And because the stack outgrows even that edge's ceiling, the panel animates its height to
    // the prediction over the roll's own duration. Left to `auto` it grew one-for-one until the cap
    // applied, so the chat's window was squeezed only in the roll's tail: the empty state held its
    // size and then resized at the end. Animated, the window compresses in step with the stack and
    // everything arrives at its final size.
    expect(moves).toEqual([
      { from: { height: 400, bottom: 300 }, to: { height: 580, bottom: 300 } },
    ]);
    expect(durations).toEqual([300]);
  });

  it("counts an aside that is only STANDING off an arriving roll's prediction too", () => {
    // Ctrl+N with the switcher list open: one commit summons the panel and rolls that list shut,
    // and the reminder stack is present in the panel throughout. The roll is not the aside, so the
    // ride-along counted the stack into the height it centred on while the placement at the end of
    // the roll counted it out again, and the two disagreed by a whole stack. Measured at 900x1000
    // over the demo: the summon pinned 227 and the placement at the end re-centred to 324, so a
    // touch inside the arrival window, which stops that placement re-centring, left the session
    // 97px low for the rest of it.
    const tick = clock();
    const { ref, element, state, bottom } = harness();
    const chat = view(element);
    standing(chat, 190);
    // Shut, and holding 546 of chat and stack plus 120 of switcher list.
    state.natural = 666;
    const { rerender } = renderHook(({ open }) => usePanelMotion(ref, open, "chat"), {
      initialProps: { open: false },
    });
    rolling(chat, 0, 120);
    rerender({ open: true });
    // 546 arriving, less the 190 the stack takes: the chat's own 356 centres and the stack grows it
    // upward from there.
    expect(bottom()).toBe(322);

    // A key inside the arrival window hands the geometry to the session, so the placement at the
    // end of the roll no longer re-centres. There is nothing to re-centre either: the edge the
    // summon pinned is the one that measurement would have produced.
    tick(1);
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k" }));
    state.natural = 546;
    element.querySelector("[data-morphing]")?.removeAttribute("data-morphing");
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(bottom()).toBe(322);
  });

  it("bounds an arriving roll where the placement bounds it, before the aside comes off", () => {
    // The prediction and the measurement have to be counted in the same order as well as by the
    // same rule. `place` reads the panel under the loose cap and subtracts the aside from what it
    // reads, so a prediction that outgrows that cap has to be cut to it before the aside is
    // subtracted. Cut afterwards, the ride-along landed a whole aside above the placement that
    // followed it, which is a second movement on the summon rather than a wrong edge for the
    // session.
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
    // The stack rolling in takes the panel to 850, where the loosest cap any edge could allow is
    // 760: what arrives is 760, of which the stack is 250 and the chat 510.
    const section = rolling(chat, 250, 0);
    section.classList.add("collapse", "aside");
    rerender({ open: true });
    expect(bottom()).toBe(245);
    const slides = moves.length;

    // The roll lands, and the placement finds nothing to move.
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
    // Shut, and short: the conversation and the day's reminders have not been pulled yet.
    state.natural = 356;
    const { rerender } = renderHook(({ open }) => usePanelMotion(ref, open, "chat"), {
      initialProps: { open: false },
    });
    rerender({ open: true });
    // The pull lands a frame behind the summon and the panel is really 546 tall. That counts as the
    // panel arriving with its content rather than growing afterwards, so it centres on 546. Pinning
    // it to the centre of the 356 instead left it 95px above its own centre and against its ceiling
    // for the rest of the session. (An earlier version of this comment added "where every later
    // shrink slid the composer", which was true of the two-bound panel and stopped being true on
    // 2026-07-20. The cost the arrival window prevents is the off-centre session.)
    state.natural = 546;
    rerender({ open: true });
    expect(bottom()).toBe(227);
    // Once it has arrived, further growth is ordinary growth: the bottom edge holds and the top
    // rises.
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
    // The reminder stack rolls open from nothing to 190px, 10ms behind the summon. Riding along
    // with it to the centre of the 546 it is taking the panel to is one movement; pinning to the
    // edge below and re-centring when the roll ended would have been two.
    rolling(element, 190, 0);
    rerender({ open: true });
    expect(bottom()).toBe(227);
    // A slide of the bottom edge alone: the section owns the height for the length of the roll.
    expect(moves).toEqual([
      { from: { height: null, bottom: 322 }, to: { height: null, bottom: 227 } },
    ]);
    // The edge it landed on is the one the session is then pinned to, so the placement at the end
    // of the roll has nothing left to correct.
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
    // A key, one tick after the panel appeared. Growth from here is the user's own doing, so it
    // grows from the pinned edge rather than re-centring under their hand.
    tick(1);
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k" }));
    state.natural = 546;
    rerender({ open: true });
    expect(bottom()).toBe(322);
  });

  it("gives back the exact edge when a section opened inside the arrival window rolls shut", () => {
    // The defect this covers, traced at 60Hz in a 900px viewport: opening the chat switcher 410ms
    // into a summon re-pinned the panel to the centre of the 666px it was about to be, and closing
    // the list left the 546px panel on that same edge, 60px below its own centre, for the rest of
    // the session. A trip to the console and back parked the bad edge and handed it straight back.
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
    // The switcher rolls open to 400px, which is more room than there is above the panel. The edge
    // it is pinned to does not move, and the height gives way instead.
    const section = rolling(element, 400, 0);
    rerender({ open: true });
    expect(bottom()).toBe(322);
    tick(300);
    state.natural = 756;
    state.playState = "finished";
    section.removeAttribute("data-morphing");
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(bottom()).toBe(322);

    // Closing it lands on the edge the panel had before it opened, to the pixel, because that edge
    // never moved. A roll inside the arrival window used to re-pin the panel to the centre of the
    // height it was about to be, and closing the list then left it 60px below its own centre for
    // the rest of the session.
    section.setAttribute("data-morphing", "0");
    rolled(section, 400);
    rerender({ open: true });
    expect(bottom()).toBe(322);
    expect(moves).toEqual([]);
  });

  it("does not read the press that summoned the panel as the user touching it", () => {
    // The orb is clicked to maximize, so a real pointerdown lands just before the panel appears.
    // The arrival that follows it is the case the arrival window exists for.
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
    // A line of the reply lands: 22px of growth, which at this distance takes the floor.
    state.natural = 422;
    rerender();
    expect(durations).toEqual([120]);

    // 55ms later the next token arrives and leaves the height exactly where it was. Starting a
    // fresh 120ms ease here made the panel lag the text: measured over one reply, a 23px line
    // started four eases 55ms apart and settled 285ms after the words were on screen.
    tick(55);
    state.displayed = 408;
    rerender();
    expect(moves[1]).toEqual({ from: { height: 408, bottom: 300 }, to: { height: 422, bottom: 300 } });
    expect(durations[1]).toBe(65);

    // The token after that shortens the same move again, so the line settles 120ms after it
    // appeared whatever arrives while it is landing.
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
    // Another line of growth mid-ease is a different destination, so it is paced from the height on
    // screen to the new one rather than squeezed into what was left of the last move.
    tick(55);
    state.displayed = 408;
    state.natural = 530;
    rerender();
    expect(durations[1]).toBe(193);
  });

  it("predicts a roll no taller than the panel is allowed to be", () => {
    const { ref, element, state, moves, bottom } = harness();
    // Already at full height for this viewport, so there is nowhere to grow.
    state.natural = 760;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(120);
    state.playState = "finished";
    // A section rolls open from nothing to 190px. Placing for the uncapped prediction asks where a
    // 950px panel goes in a viewport that allows 760, and puts it off the bottom of the screen:
    // traced at 60Hz, the panel's bottom edge ran 108px down to the floor over the roll and came
    // back up afterwards.
    rolling(element, 190, 0);
    rerender();
    expect(bottom()).toBe(120);
    expect(moves).toEqual([]);
  });

  it("caps that prediction at the same whole-pixel ceiling the element was given", () => {
    // 720 is the body's own window, and 76% of it is 547.2: the case the test above cannot see,
    // because 76% of 1000 is already whole. The panel is given a `max-height` in whole pixels, so a
    // prediction capped at the raw 547.2 places it for a height it can never have, and the roll
    // slides the edge it was standing on. Traced at 60Hz at 640x720 with the reminder stack up
    // before this was fixed, when the edge was also written rounded: every roll inside the panel
    // began with `bottom` stepping 87 to 86 in a single frame and stepped back the frame the roll
    // ended. The edge now carries its own fraction, so the same disagreement is worth 0.2px rather
    // than a whole pixel, and the ceiling still has to agree with itself.
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

  it("takes the ceiling along in the move, riding the same edge the panel is standing on", () => {
    const { ref, state, keyed } = harness();
    state.natural = 700;
    const { rerender } = renderHook(({ view }) => usePanelMotion(ref, true, view), {
      initialProps: { view: "chat" },
    });
    state.playState = "finished";
    state.natural = 300;
    rerender({ view: "console" });
    // The edge holds at 150, so the ceiling is 880 less 150 at both ends of the move, and the
    // from-frame's cap never sits below the height the ease starts from. The clamped-first-frame
    // defect this once covered now belongs to the slide, and is covered by the flipped-switch test
    // above, where the bottom edge rises mid-move.
    expect(keyed.at(-1)).toEqual([
      { height: "700px", bottom: "150px", maxHeight: "730px" },
      { height: "300px", bottom: "150px", maxHeight: "730px" },
    ]);
  });

  it("centres the arriving view on itself, not shy of an aside the leaving view still holds", () => {
    // Centring on a view change lives behind the flipped switch, so this defect is driven through
    // `place` as the slide's own test is. The chat holds the reminder stack (an aside): the panel
    // centres on the conversation and the stack grows it upward.
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

    // Into the console, which has no stack of its own. The chat is held for one morph as `.view.out`
    // with its stack still in it, and subtracting that from the height of the arriving view centred
    // a 300px console as though it were 100px. Measured at 640x720: the console sat 96px above the
    // middle of the screen and, the ceiling being measured from the edge it sits on, was capped at
    // 351px where 448 would have fitted, leaving four spare pixels in the whole view.
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
    // A roll is not a placement, and nothing removes the measuring cap until the roll ends, so a
    // loose cap left in place lets the section roll the panel past the clear space kept above it.
    // Traced at 60Hz at 640x720 with the panel already on its ceiling, opening the chat switcher:
    // the panel went to the loose 547 with its top edge 11px off the top of the screen, stayed
    // there for the whole 300ms roll, and the placement at the end put the real 450 back in a
    // single frame. Held at the real cap for the duration, the section rolls to its full height and
    // the history gives up the room instead.
    rolling(element, 190, 0);
    rerender();
    expect(element.style.maxHeight).toBe("580px");
    // And on every render inside the same roll, since each one writes the measuring cap first.

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

    // A section rolls open to more than there is room for: 400 less nothing plus 190 is 590, and the
    // panel may only be 580 tall from the edge it sits on, so the roll ends on the ceiling.
    const section = rolling(element, 190, 0);
    state.natural = 590;
    rerender();
    expect(element.style.maxHeight).toBe("580px");
    expect(moves).toEqual([]);

    // The roll ends and the panel is already where it is going, so there is nothing left to animate.
    // Read under the measuring cap instead of off the screen it reads 590, and the panel eases 590
    // to 580: traced at 640x720, a 97px jump to a top edge 11px off the screen and a slide back
    // down, one frame after a roll that had just held the ceiling perfectly for its whole length.
    section.removeAttribute("data-morphing");
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(moves).toEqual([]);
    expect(bottom()).toBe(300);
  });

  it("hands back a scroll position that its own measurement clamped", () => {
    const { ref, element, state } = harness();
    state.natural = 400;
    // At rest the box can scroll to 400; while the panel is being measured it is taller, and can
    // hold only 80. A reader at 120 is inside the difference, which is where the defect lived.
    const history = scrollBox(element, 400, 80);
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    history.scrollTop = 120;

    // Any placement at all: a token landing, a section rolling, the window resizing. Before this,
    // every one of them moved the log up under the reader by exactly the difference above, which
    // the user reported as the history not letting them scroll while a reply streams.
    state.playState = "finished";
    state.natural = 420;
    rerender();
    expect(history.scrollTop).toBe(120);

    // Including the roll path, which returns from the middle of `place` and has its own way out.
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
    // Every rendered token cancels the running ease and starts another, so a streamed reply is a
    // long series of tiny moves. One line of growth takes the floor and lands before the next
    // token arrives, instead of restarting a long ease that never converges.
    state.playState = "finished";
    state.natural = 422;
    rerender({ view: "chat" });
    expect(durations).toEqual([120]);
    // Half a view's worth of travel is paced between the two ends.
    state.natural = 552;
    rerender({ view: "chat" });
    expect(durations[1]).toBe(206);
    // A whole view changing moves the top edge 262px, past the travel that earns the full duration,
    // so it takes the ceiling.
    state.natural = 180;
    rerender({ view: "console:appearance" });
    expect(durations[2]).toBe(380);
  });

  it("publishes every cap it writes, so the sections are budgeted against the panel's own number", () => {
    // The sections in the panel's chrome are capped out of this number (overlay.css reads it), so
    // the panel must never sit under one ceiling while they are sized for another. Asserted at each
    // of the three caps a placement writes, because they are three different numbers: the loose
    // measuring cap, the cap a roll leaves in place, and the real ceiling of the edge the panel
    // settles on.
    const { ref, element, state, bottom } = harness();
    state.capped = true;
    state.natural = 300;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(350);
    expect(element.style.maxHeight).toBe("530px");
    expect(element.style.getPropertyValue(CEILING_PROPERTY)).toBe("530px");
    // A roll owns the height, and the placement returns early having written only the roll's cap.
    state.playState = "finished";
    const section = rolling(element, 400, 0);
    rerender();
    expect(element.style.getPropertyValue(CEILING_PROPERTY)).toBe(element.style.maxHeight);
    // And the panel places itself again at the end of the roll, on a new edge.
    section.remove();
    state.natural = 760;
    rerender();
    expect(element.style.maxHeight).toBe(`${maxHeight(VIEWPORT, bottom())}px`);
    expect(element.style.getPropertyValue(CEILING_PROPERTY)).toBe(element.style.maxHeight);
  });

  it("stops growing at the top rather than reclaiming room by growing downward", () => {
    const { ref, state, bottom } = harness();
    // A short panel, centred low enough that growing without bound would run off the top.
    state.natural = 300;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(350);
    state.natural = 760;
    rerender();
    // The edge holds and the cap does the work: 880 - 350 leaves the top exactly on the 12% line.
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
    // A height animation overrides the measured height, so reading it mid-ease returns the
    // in-flight value. Animating from in-flight to in-flight never converges, and during a stream
    // the panel sat permanently short of its content with the text clipped.
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
    // From the height on screen (360) to the true content height rather than the in-flight one.
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

    // A section 60px tall starts rolling shut. It animates its own height and the panel's `auto`
    // height follows frame by frame, so the panel must not animate the same pixels against it. The
    // panel is nowhere near its ceiling here, so it has no slide of its own to make.
    const section = rolling(element, 0, 60);
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

  it("leaves the bottom edge alone through a roll, since growth no longer costs it anything", () => {
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 300;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.playState = "finished";
    state.natural = 600;
    rerender();
    expect(bottom()).toBe(350);

    // A section rolls open from nothing to 100px, taking the panel past what fits above it. The
    // height gives way instead, so the edge the composer sits on stays where it is and the roll is
    // the whole movement on screen.
    rolling(element, 100, 0);
    rerender();
    expect(bottom()).toBe(350);
    expect(moves).toHaveLength(1);
  });

  it("has nothing left to move when a roll it followed ends", () => {
    // A section rolling open finishes without changing any state, so no render follows it and this
    // event is the panel's only notification of it. The panel is already where the roll was taking
    // it, so there is nothing to animate and animating anything would be a second movement.
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
    // Still rolling: the section owns the height, and the panel keeps its hands off.
    expect(moves).toHaveLength(1);

    section.removeAttribute("data-morphing");
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(bottom()).toBe(350);
    expect(moves).toHaveLength(1);
  });

  it("corrects itself when a roll ends somewhere other than where it said it would", () => {
    // The prediction is one section's word for its own height; the panel can be resized by
    // something else while the roll runs. Re-measuring at the end is what keeps that honest.
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 300;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.playState = "finished";
    state.natural = 600;
    rerender();
    const section = rolling(element, 100, 0);
    rerender();

    // The roll ends with the panel 760 tall, not the 700 it was told to expect. Re-measuring is
    // still what keeps the panel honest about its height; what has changed is that the correction
    // costs the bottom edge nothing, because the edge was never part of the roll.
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

    // Half way through, the section is told to roll back shut. There is nothing to reverse: the
    // panel never joined in, so the only thing that turns around is the roll itself.
    state.playState = "running";
    state.natural = 650;
    section.setAttribute("data-morphing", "0");
    rolled(section, 50);
    rerender();
    expect(bottom()).toBe(350);
    expect(moves).toHaveLength(1);
  });

  it("carries a height ease that was still in the air through the roll that interrupted it", () => {
    // The regression this covers: the roll cancelled the panel's running height ease and issued a
    // slide of the bottom edge alone, which handed the used height straight back to layout. Traced
    // in a browser at 60Hz, acking a reminder and opening the switcher 40ms later dropped the
    // panel's top edge 61px in a single frame with nothing animating it.
    const { ref, element, state, moves, durations, bottom } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(300);
    // A reminder is acked: the panel starts easing 400 down to 340.
    state.natural = 340;
    rerender();
    expect(moves[0]).toEqual({ from: { height: 400, bottom: 300 }, to: { height: 340, bottom: 300 } });

    // Part way through that, with the panel 380 tall and still moving, the switcher rolls open from
    // nothing to 100px. The height goes on being animated: from where the eye has it, to where the
    // roll will leave the panel (340 of its own, less the 0 the section takes, plus the 100 coming).
    state.displayed = 380;
    const section = rolling(element, 100, 0);
    rerender();
    expect(moves[1]).toEqual({ from: { height: 380, bottom: 300 }, to: { height: 440, bottom: 300 } });
    // Over the roll's own duration, so the residue decays exactly as the section opens.
    expect(durations[1]).toBe(300);

    // The reply grew another line while the roll ran, so the panel is really 470 tall and not the
    // 440 it drove itself to. That residue is eased away rather than snapped.
    state.natural = 470;
    section.removeAttribute("data-morphing");
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(moves[2]).toEqual({ from: { height: 440, bottom: 300 }, to: { height: 470, bottom: 300 } });
    expect(durations[2]).toBe(120);
  });

  it("rides along with a roll no render told it about, which is how a reply's trace opens", () => {
    // Every section above lives in the panel's own chrome and opens on overlay state, so the panel
    // re-rendered alongside it and its layout effect found the roll for free. A reply's Thoughts
    // disclosure owns its open state locally: nothing above that message renders when it is
    // clicked, and the panel used to hear only the END of the roll. Traced at 60Hz in a 900px
    // viewport before the start event existed: the trace rolled open over 300ms with the panel's
    // height following it, and then the panel, placing itself from the geometry it remembered from
    // before the roll, snapped back to its old height for one frame and eased 76px up and 43px down
    // all over again.
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 600;
    renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(200);

    // No rerender anywhere: the section sets the attribute and says so, and that is the whole
    // notice the panel gets.
    rolling(element, 100, 0);
    element.dispatchEvent(new CustomEvent("cortex:morphstart", { bubbles: true }));
    // Taking the panel past what fits above it costs the edge nothing now, so the start event has
    // nothing to set in motion. It still has to be HEARD: the geometry the panel remembers is
    // brought up to date by it, and the defect below is what happens when it is not.
    expect(bottom()).toBe(200);
    expect(moves).toEqual([]);

    // And when that roll lands there is nothing left to move, which is the defect stated as a test.
    state.natural = 700;
    element.querySelector("[data-morphing]")?.removeAttribute("data-morphing");
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(bottom()).toBe(200);
    expect(moves).toHaveLength(0);
  });

  it("places a roll announced mid-commit for the render on screen, not the one before it", () => {
    // Ctrl+N, or cycling to another chat, while the panel is minimized with the switcher list open:
    // one commit both summons the panel and rolls that list shut (`newChat`/`openSession` set
    // `mode: "panel"` and `switcherOpen: false` together). `Collapse` announces its roll from its
    // own layout effect, which is a CHILD of this hook's and so runs before it, and long before any
    // passive effect of that render has re-subscribed anything. So the handler that hears this one
    // is the PREVIOUS render's, and if it read the panel's state out of its own closure it would
    // place the panel for a panel that is still shut: the summon would not be seen arriving, and it
    // would come back to the edge the last session left it on instead of centred on what it arrives
    // with. Hence the placement is read from a ref assigned during the render.
    const { ref, element, state, moves, bottom } = harness();
    // Shut, and still holding the 200px of switcher list.
    state.natural = 500;
    const { rerender } = renderHook(
      ({ open, roll }) => {
        // Stands in for the `Collapse` inside the panel: same phase, same ordering, declared before
        // the hook under test so it commits first exactly as a child's effect does.
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
    // It arrives 300 tall (500, less the 200 the list is handing back) and centred on that, riding
    // the roll's own 300ms rather than correcting itself in a second beat afterwards.
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
    // Both ends of the roll, since both are listened for on the same element.
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
    // Mid-ease the panel is shorter than what it is easing to, so the history overflows for a few
    // frames and flashes a scrollbar for a height the panel never settles at. The stylesheet hides
    // the thumb while this is set; the attribute is the whole of the panel's part in it.
    expect(element.hasAttribute("data-resizing")).toBe(true);
    played[0]?.onfinish?.();
    expect(element.hasAttribute("data-resizing")).toBe(false);
    // A render that finds nothing to move clears it synchronously, on the spot. Clearing from the
    // animation's own cancel event was the first attempt and is wrong: `oncancel` is dispatched
    // asynchronously, so during a stream it landed AFTER the replacing animation had set the flag
    // again, and wiped it. Traced at 60Hz, 19 frames of one reply overflowed unmarked because of it.
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
    // Never placed, so it takes the edge it would open at: that is what makes the first summon
    // appear centred instead of sliding there.
    const { rerender } = renderHook(({ open }) => usePanelMotion(ref, open, "chat"), {
      initialProps: { open: false },
    });
    expect(bottom()).toBe(300);

    // Open, and grown to where a conversation and an open switcher put it.
    state.playState = "finished";
    state.natural = 700;
    rerender({ open: true });
    expect(bottom()).toBe(150);

    // Dismissed. The panel is scaled away from where the eye has it, so nothing about its geometry
    // moves: written in the frame of the dismiss, the edge for the NEXT summon lands while the panel
    // is still full size and fully opaque, which at 640x720 was the window dropping 78px and growing
    // 58 in one frame before it began to shrink away.
    state.natural = 400;
    rerender({ open: false });
    expect(bottom()).toBe(150);
    // And the summon still comes back to the middle, which is where that edge was always for: the
    // arrival window centres on what the panel arrives WITH, so the dismiss never had to.
    rerender({ open: true });
    expect(bottom()).toBe(300);
    expect(moves).toEqual([]);
  });

  it("eases a resize no render told it about, such as a row released at the end of its exit", () => {
    // A resize the panel is never asked to place itself for: its `auto` height simply followed in
    // the frame the content landed, bottom edge pinned, with no ease at all. The composer's growth
    // was the largest example while the draft lived in `Composer`'s own state (traced at 640x720
    // with the reminder stack acked, two consecutive samples and no third between them: 16px for a
    // further line on a stacked pill, 36px for the character that restacks a one-line draft, 52px
    // for a Shift+Enter that restacks and adds a line at once, and 98px for a paste that fills the
    // field to its 120px ceiling). It is an ordinary render now that the draft is state above the
    // composer, and what is left here is a released row and content that settles late, which reach
    // the panel exactly as that growth did.
    const { ref, element, state, moves, durations } = harness();
    state.natural = 400;
    renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 452;
    expect(resized(element)).toBe(1);
    expect(moves).toEqual([{ from: { height: 400, bottom: 300 }, to: { height: 452, bottom: 300 } }]);
    // Paced by the distance like any other move, and pinned by the bottom edge like any other
    // growth inside the chat: the composer does not slide out from under the hand that typed it.
    expect(durations).toEqual([120]);
  });

  it("leaves the height alone while a section inside is rolling it, frame by frame", () => {
    // A roll is one notification per frame for its whole length (19 across a 300ms roll, measured
    // at 900x900 over the demo's reminder pull). The section owns the height through all of them
    // and the ride-along has already taken the bottom edge where the roll will leave it, so a
    // placement on those frames is the panel's arithmetic against a height that is mid-animation
    // by construction.
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
    // And the roll's own start event is still what the panel rides along with: the observer did
    // not quietly answer it first and leave the start with nothing to do.
    element.dispatchEvent(new CustomEvent("cortex:morphstart", { bubbles: true }));
    expect(bottom()).toBe(205);
    expect(moves).toHaveLength(1);
  });

  it("leaves its own move in the air rather than retargeting it once a frame", () => {
    // The panel's ease is a height animation on this same element, so it is also one notification
    // per frame (18 across one 380ms move in the same trace). Answering them by the box would cancel
    // the move to measure the natural box and start another, sixty times a second, which is feeding
    // the observer its own output: measured over one 150px growth with the guard taken off, 24
    // animations replaced 2, the ease restarted its own curve every frame so the panel crawled 33px
    // in the first 233ms, and it then dumped 40.83px in a single frame at the end.
    //
    // What settles those frames is that the height the panel WANTS has not moved, so there is
    // nothing behind any of them. The ease is not consulted about it at all.
    const { ref, element, state, moves } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 520;
    rerender();
    expect(moves).toHaveLength(1);
    state.displayed = 460;
    expect(resized(element)).toBe(1);
    expect(moves).toHaveLength(1);

    // And once it has landed, a box that is still the height it was placed for is still nothing.
    state.playState = "finished";
    expect(resized(element)).toBe(1);
    expect(moves).toHaveLength(1);
  });

  it("joins the move it is already making when content grows inside it", () => {
    // A growth that lands mid-move used to wait for that move, because the running height animation
    // overrides the box and hides it. Traced at 900x1000 with 150px appended into the log and 40px
    // more 100ms into the resulting 255ms ease: the second growth was invisible for 188ms, the frame
    // that handed the element back read 514, and only then did a second ease start. Asked what the
    // panel WOULD be instead, the same trace answers the 40px one frame later and the panel is
    // settled at 339ms rather than 465ms.
    const { ref, element, state, moves, durations } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 520;
    rerender();
    expect(moves).toHaveLength(1);

    // Mid-ease: the box is at 460 and the content now wants 560. The box cannot say so, which is
    // why the probe exists, and the move is redirected from where the eye has it rather than from
    // where it was going.
    state.displayed = 460;
    state.natural = 560;
    expect(resized(element)).toBe(1);
    expect(moves).toEqual([
      { from: { height: 400, bottom: 300 }, to: { height: 520, bottom: 300 } },
      { from: { height: 460, bottom: 300 }, to: { height: 560, bottom: 300 } },
    ]);
    // Paced by what is left to travel, like any other move, rather than by the whole 160.
    expect(durations.at(-1)).toBe(158);
    // And the probe hands the box straight back: an element left declaring `height: auto` important
    // would never follow another animation again, and one left with an important cap would keep the
    // sections it feeds on a budget nothing updates.
    expect(element.style.getPropertyValue("height")).toBe("");
    expect(element.style.getPropertyPriority("max-height")).toBe("");
    expect(element.style.maxHeight).toBe("580px");
  });

  it("opens a retarget on the sub-pixel the panel is standing at, and ends on the edge it wrote", () => {
    // A used height is fractional and `offsetHeight` was not, so every retarget opened its keyframes
    // on the whole pixel below the one the eye had and the panel stepped back by the remainder for a
    // frame. Instrumented at 900x1000 over one streamed reply before this: 310 of 330 readings threw
    // a sub-pixel away, worst 0.484, all three of the moves opened on a whole number, and the painted
    // top edge stepped back 0.281px. After, none of six openings is whole and the worst step is
    // 0.015px, which is Chromium's own 1/64px grid.
    //
    // The bottom edge is the same defect on the other axis: written rounded while the keyframe went
    // to the fraction, the whole ease painted 324.5 and the frame that took the animation away
    // handed back 325 (measured at 901x1001). Both ends of the move now agree with what the element
    // is standing on.
    // On Chromium's own 1/64px grid, which is what a used height comes back on.
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
    // A render that grows the panel is answered by the placement inside that render, and that
    // placement resizes the element the watch is on. Measured against the height last LOOKED at, the
    // notification one frame later reads as growth and places a second time: instrumented over one
    // streamed reply at 900x1000, that doubled every move, 6 animations for 3 growths, each pair
    // 3ms and 0.015px apart. Measured against the height the panel was PLACED for, there is nothing
    // there.
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
    // Placing is itself a resize of the element being watched, and an observer that resizes its own
    // target inside its own callback is the one case the specification's depth rule cannot deliver:
    // the notification is dropped and the page told through the "loop completed with undelivered
    // notifications" error. Measured over the demo before this, one error event per keystroke that
    // grew the pill.
    const frame = frames();
    const { ref, element, state, moves } = harness();
    state.natural = 400;
    renderHook(() => usePanelMotion(ref, true, "chat"));
    state.natural = 452;
    expect(resized(element)).toBe(1);
    expect(moves).toHaveLength(1);

    // Nothing is watching for the rest of this frame, which is what leaves the specification's
    // re-gather with nothing to drop.
    state.playState = "finished";
    state.natural = 500;
    expect(resized(element)).toBe(0);
    expect(moves).toHaveLength(1);

    // And on the next frame the watch is back, so the growth that landed meanwhile is still eased.
    frame.run();
    expect(resized(element)).toBe(1);
    expect(moves).toHaveLength(2);

    // A reading with nothing behind it is heard and answered with nothing, which is what makes the
    // callback settle rather than chase the box it just moved. The watch is not lifted for it
    // either, so it is still there for the next one: lifting on every delivery would spend a frame
    // of blindness and a placement on each of them for as long as the panel is open.
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
    // And nothing takes the watch back up behind the unmount.
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
    // Nothing is listening at all, which is stronger than nothing happening: a watch left running
    // holds the element and the memory of a panel that is gone.
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
