import { renderHook } from "@testing-library/react";
import { useLayoutEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { usePanelMotion } from "./usePanelMotion";

const VIEWPORT = 1000;

interface Move {
  /** null when the move has no `height` in it at all: a slide of the bottom edge alone. */
  readonly from: { height: number | null; bottom: number };
  readonly to: { height: number | null; bottom: number };
}

/**
 * A stand-in for the browser's geometry animation, faithful in the ways that matter: while an
 * animation runs it OVERRIDES the properties it animates and nothing else, and a FINISHED animation
 * stops overriding them while still being the last animation the hook holds. That last one is what
 * the first version of this hook got wrong: it treated any non-null animation as live, read the
 * finished one's measurement as "what is displayed", and so animated only every other size change.
 * Measured in a browser: opening the chat switcher jumped, closing it eased, opening it jumped.
 */
function harness() {
  const element = document.createElement("div");
  const state = {
    natural: 0,
    displayed: 0,
    /** Where a running slide has got to, when a test wants to interrupt one mid-flight. */
    displayedBottom: null as number | null,
    playState: "running" as AnimationPlayState,
  };
  const moves: Move[] = [];
  const played: { onfinish: (() => void) | null; oncancel: (() => void) | null }[] = [];
  const durations: number[] = [];
  const cancels: number[] = [];
  let running = false;
  let animatesHeight = false;

  // Only a LIVE animation overrides the box: one that has finished without a fill has handed the
  // element back to its own layout, even though the hook is still holding on to it.
  const live = () => running && state.playState === "running";
  const height = () => (live() && animatesHeight ? state.displayed : state.natural);
  // The hook reads the HEIGHT off `offsetHeight` and only the bottom edge off the rect, because the
  // rect is measured after the panel's summon transform and the layout box is not.
  Object.defineProperty(element, "offsetHeight", { get: height });
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
  return { element, ref, state, moves, durations, cancels, played, bottom };
}

/** How tall a rolling section is right now, which changes under it while the roll runs. */
function rolled(section: HTMLElement, height: number): void {
  Object.defineProperty(section, "offsetHeight", { get: () => height, configurable: true });
}

/** A section rolling to `target` and `height` tall right now, as `Collapse` leaves it in the DOM. */
function rolling(parent: HTMLElement, target: number, height: number): HTMLElement {
  const section = document.createElement("div");
  section.setAttribute("data-morphing", String(target));
  rolled(section, height);
  parent.append(section);
  return section;
}

/**
 * A clock the tests can move, because a summon owns the panel's geometry for a fixed window
 * afterwards. Everything a test does otherwise happens inside the same millisecond, which is the
 * honest simulation of a summon and the content landing behind it.
 */
function clock(): (ms: number) => void {
  let now = 1_000_000;
  vi.spyOn(Date, "now").mockImplementation(() => now);
  return (ms: number) => {
    now += ms;
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

  it("re-centres on a view change, sliding and resizing in one movement", () => {
    const { ref, state, moves, bottom } = harness();
    state.natural = 700;
    const { rerender } = renderHook(({ view }) => usePanelMotion(ref, true, view), {
      initialProps: { view: "chat" },
    });
    expect(bottom()).toBe(150);
    // The console is much shorter: the panel shrinks to it AND returns to true centre.
    state.natural = 300;
    rerender({ view: "console:shortcuts" });
    expect(bottom()).toBe(350);
    expect(moves).toEqual([{ from: { height: 700, bottom: 150 }, to: { height: 300, bottom: 350 } }]);
  });

  it("restores the chat's own edge on the way back, rather than centring it a second time", () => {
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
    // The console is a different view, so it centres for its own much shorter height.
    state.natural = 200;
    rerender({ view: "console:appearance" });
    expect(bottom()).toBe(400);
    // Coming back is not a new arrival: the chat has not changed while it was away, so it returns
    // to the edge it was left at rather than to (1000 - 560) / 2 = 220.
    state.natural = 560;
    rerender({ view: "chat" });
    expect(bottom()).toBe(300);
    expect(moves[2]).toEqual({ from: { height: 200, bottom: 400 }, to: { height: 560, bottom: 300 } });
  });

  it("centres a first arrival at the chat, having nothing parked to put it back on", () => {
    const { ref, state, bottom } = harness();
    state.natural = 300;
    const { rerender } = renderHook(({ view }) => usePanelMotion(ref, true, view), {
      initialProps: { view: "console:appearance" },
    });
    expect(bottom()).toBe(350);
    state.natural = 500;
    rerender({ view: "chat" });
    expect(bottom()).toBe(250);
  });

  it("caps the height at the ceiling instead of walking the bottom edge down to meet it", () => {
    const { ref, state, bottom } = harness();
    state.natural = 400;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(bottom()).toBe(300);
    // A section rolls open and the panel wants more room than there is above it. Growth is upward
    // or it does not happen: the edge the composer sits on does not move, and the panel simply
    // stops getting taller at 880 - 300, which puts its top edge on the 12% line.
    state.natural = 700;
    rerender();
    expect(bottom()).toBe(300);
    expect(ref.current.style.maxHeight).toBe("580px");
    // Closing it again changes nothing about the edge either, so a round trip is a round trip.
    state.natural = 400;
    rerender();
    expect(bottom()).toBe(300);
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
    // The pull lands a beat behind the summon and the panel is really 546 tall. That is the panel
    // ARRIVING with its content, not growing after the fact, so it centres on it. Pinning it to the
    // centre of the 356 instead left it 95px above its own centre and hard against its ceiling for
    // the rest of the session, where every later shrink slid the composer.
    state.natural = 546;
    rerender({ open: true });
    expect(bottom()).toBe(227);
    // Once it has arrived, the same growth is growth: the bottom edge holds and the top rises.
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
    // with it to the CENTRE of the 546 it is taking the panel to is one movement; pinning to the
    // edge below and re-centring when the roll ended would have been two.
    rolling(element, 190, 0);
    rerender({ open: true });
    expect(bottom()).toBe(227);
    // A slide, and only a slide: the section owns the height and the panel takes its edge along.
    expect(moves).toEqual([
      { from: { height: null, bottom: 322 }, to: { height: null, bottom: 227 } },
    ]);
    // And the edge it landed on is the one the session is then pinned to: the placement at the end
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
    // A key, a beat after the panel appeared. Whatever grows from here is the user's doing, so it
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
    // it is pinned to does not move for that, and now neither does anything else: the height is
    // what gives way.
    const section = rolling(element, 400, 0);
    rerender({ open: true });
    expect(bottom()).toBe(322);
    tick(300);
    state.natural = 756;
    state.playState = "finished";
    section.removeAttribute("data-morphing");
    element.dispatchEvent(new CustomEvent("cortex:morphend", { bubbles: true }));
    expect(bottom()).toBe(322);

    // Closing it lands on the edge the panel had before it opened, to the pixel, and gets there by
    // never having left it. The edge a summon centres on is the edge the session keeps: a roll
    // inside the arrival window used to re-pin the panel to the centre of the height it was about
    // to be, and closing the list then stranded it 60px below its own centre for the session.
    section.setAttribute("data-morphing", "0");
    rolled(section, 400);
    rerender({ open: true });
    expect(bottom()).toBe(322);
    expect(moves).toEqual([]);
  });

  it("does not read the press that summoned the panel as the user touching it", () => {
    // The orb is clicked to maximize, so a real pointerdown lands a beat BEFORE the panel appears.
    // The arrival that follows it is exactly the case the window exists for.
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
    // fresh 120ms ease here is what made the panel chase the text: measured over one reply, a 23px
    // line started four eases 55ms apart and settled 285ms after the words were on screen.
    tick(55);
    state.displayed = 408;
    rerender();
    expect(moves[1]).toEqual({ from: { height: 408, bottom: 300 }, to: { height: 422, bottom: 300 } });
    expect(durations[1]).toBe(65);

    // And the token after that shortens the same move again. The line lands 120ms after it
    // appeared, whatever arrives while it is landing.
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
    // Another line of growth mid-ease is a different destination, so it is paced from where the eye
    // is to where the panel is now going, and not squeezed into what was left of the last move.
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
    // A section rolls open from nothing to 190px. Taking that prediction at face value asks where a
    // 950px panel goes in a viewport that allows 760, and the answer is off the bottom of the
    // screen: traced at 60Hz, the panel's bottom edge ran 108px down to the floor over the roll and
    // came back up afterwards.
    rolling(element, 190, 0);
    rerender();
    expect(bottom()).toBe(120);
    expect(moves).toEqual([]);
  });

  it("caps that prediction at the same whole-pixel ceiling the element was given", () => {
    // 720 is the body's own window, and 76% of it is 547.2: the one case the test above cannot see,
    // because 76% of 1000 is already whole. The panel is given a `max-height` in whole pixels, so a
    // prediction capped at the raw 547.2 places it for a height it can never have. The gap is 0.2px,
    // far under `MIN_DELTA_PX`, so nothing animates it away; the bottom edge is written rounded, and
    // 86.6 and 86.4 round apart. Traced at 60Hz at 640x720 with the reminder stack up before this
    // was fixed: every roll inside the panel began with `bottom` stepping 87 to 86 in a single frame
    // and stepped back the frame the roll ended.
    vi.spyOn(window, "innerHeight", "get").mockReturnValue(720);
    const { ref, element, state, moves, bottom } = harness();
    state.natural = 547;
    const { rerender } = renderHook(() => usePanelMotion(ref, true, "chat"));
    expect(element.style.maxHeight).toBe("547px");
    expect(bottom()).toBe(87);
    state.playState = "finished";
    rolling(element, 76, 0);
    rerender();
    expect(bottom()).toBe(87);
    expect(moves).toEqual([]);
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
    // A whole view changing moves the top edge 262px, which is past the travel that earns the full
    // duration, so it takes the ceiling and not a millisecond more.
    state.natural = 180;
    rerender({ view: "console:appearance" });
    expect(durations[2]).toBe(380);
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

    // A section 60px tall starts rolling shut. It animates its own height and the panel's `auto`
    // height follows frame by frame, so the panel must not animate the same pixels against it. The
    // panel is nowhere near its ceiling here, so it has no slide of its own to make either.
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

    // A section rolls open from nothing to 100px, taking the panel past what fits above it. There
    // is nothing for the panel to do about that any more: the height gives way instead, so the
    // edge the composer sits on stays where it is and the roll is the whole movement on screen.
    rolling(element, 100, 0);
    rerender();
    expect(bottom()).toBe(350);
    expect(moves).toHaveLength(1);
  });

  it("has nothing left to move when a roll it followed ends", () => {
    // A section rolling OPEN finishes without changing any state, so no render follows it: this
    // event is the panel's only word that it happened. Having already gone where the roll was
    // taking it, there is nothing to animate here, and animating anything would be a second beat.
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
    // A cancel clears it too. During a stream that is the common ending: the next token's render
    // replaces the move, and sets the attribute again on its way out.
    state.natural = 600;
    rerender();
    expect(element.hasAttribute("data-resizing")).toBe(true);
    played[1]?.oncancel?.();
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
