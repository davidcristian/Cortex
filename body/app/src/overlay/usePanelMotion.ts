import { type RefObject, useEffect, useLayoutEffect, useRef } from "react";

import { MORPHING_ATTRIBUTE, MORPH_END_EVENT } from "./morph";

// The panel's vertical geometry, and the motion between one geometry and the next. Two rules
// share this hook because they are the same measurement:
//
//   1. A VIEW CHANGE re-centres. Opening the shortcuts view, opening settings, coming back to the
//      chat, switching chats: the panel resizes to what the new view needs and slides so that it
//      sits in the true middle of the screen again.
//   2. GROWTH INSIDE A VIEW pushes the top edge up. A reply arriving, the switcher list opening,
//      the composer taking a second line: the bottom stays pinned where it was, so the composer
//      never slides out from under the hand that just typed into it.
//
// Why this is code and not a CSS transition: a `transition: height` never fires here, because the
// panel's height is `auto` on both sides and only its *content* changed, which is not a computed
// value change. `interpolate-size: allow-keywords` does not help either; it makes `auto`
// interpolable against a LENGTH (`height: 0` to `height: auto`), not one content-driven `auto`
// against the next. Measured in a browser before this was written: with the transition declared
// and `interpolate-size` set, opening the switcher moved the panel through exactly one distinct
// height. So the old geometry is captured before paint and replayed as a real animation.

/** How long a resize or a re-centring takes, and on what curve (matches `--ease` in overlay.css). */
const DURATION_MS = 380;
const EASING = "cubic-bezier(0.4, 0, 0.2, 1)";

/** Below this many pixels a change is not worth animating (a rounding wobble, not a move). */
const MIN_DELTA_PX = 2;

/** The tallest the panel may grow, as a fraction of the viewport. Owned here rather than in CSS
 *  because the ceiling below is derived from it and the two must not drift apart. */
const MAX_HEIGHT_RATIO = 0.76;

/** The clear space kept above the panel, as a fraction of the viewport. Derived so that a panel at
 *  full height is EXACTLY centred: growth pushes the top edge up until it reaches this ceiling,
 *  and past that the panel grows downward instead, ending centred rather than jammed at the top. */
const MIN_TOP_RATIO = (1 - MAX_HEIGHT_RATIO) / 2;

interface Geometry {
  readonly height: number;
  /** Distance from the bottom of the viewport to the panel's bottom edge, in px. */
  readonly bottom: number;
}

interface Memory {
  /** The geometry currently on screen, or null before the first measurement. */
  shown: Geometry | null;
  running: Animation | null;
  /** The view the panel last settled into; anything else re-centres. */
  view: string;
  bottom: number;
  /** Set while a child owned the last size change, and cleared by the first placement after it. */
  deferred: boolean;
}

function frame(height: number, bottom: number): Keyframe {
  return { height: `${height}px`, bottom: `${bottom}px` };
}

/** Where the element is right now, mid-animation: what the eye actually sees. */
function measure(element: HTMLElement, viewport: number): Geometry {
  const rect = element.getBoundingClientRect();
  return { height: rect.height, bottom: viewport - rect.bottom };
}

function settled(from: Geometry, to: Geometry): boolean {
  return (
    Math.abs(to.height - from.height) < MIN_DELTA_PX &&
    Math.abs(to.bottom - from.bottom) < MIN_DELTA_PX
  );
}

interface Placement {
  readonly open: boolean;
  readonly view: string;
  /** Re-centre even though the view did not change (the viewport itself moved). */
  readonly recentre: boolean;
}

/**
 * Put the panel where it belongs, and animate it there from wherever it was.
 *
 * **The running animation is cancelled before measuring.** A height animation overrides the used
 * height, so measuring while one runs returns the in-flight value, not the natural one. Reading it
 * anyway is the bug this note exists to prevent: during a stream every token would animate from
 * in-flight to in-flight, the panel would never converge on its content height, and the text would
 * sit permanently clipped by the panel's `overflow: hidden`. So the order is: read what is
 * displayed, cancel, read the natural geometry, animate between the two. That also keeps a change
 * mid-ease continuous, because the new animation starts exactly where the old one was.
 */
function place(element: HTMLElement | null, memory: Memory, at: Placement): void {
  if (element === null) {
    return;
  }
  const viewport = window.innerHeight;
  element.style.maxHeight = `${Math.round(viewport * MAX_HEIGHT_RATIO)}px`;
  if (element.querySelector(`[${MORPHING_ATTRIBUTE}]`) !== null) {
    // A section inside is collapsing open or shut, and it owns this motion: the panel's `auto`
    // height follows the section's animated one frame by frame, which is what makes the two read
    // as a single movement. Record what the eye sees so a later change eases from here.
    memory.shown = { height: element.getBoundingClientRect().height, bottom: memory.bottom };
    memory.deferred = true;
    return;
  }
  const deferred = memory.deferred;
  memory.deferred = false;
  const was = memory.bottom;
  const live = memory.running !== null && memory.running.playState === "running";
  const inFlight = live ? measure(element, viewport) : null;
  memory.running?.cancel();
  memory.running = null;
  const height = element.getBoundingClientRect().height;
  // Straight after a child-owned change, the height on screen is ALREADY the new one: the panel
  // followed the roll to its end. Remembering the mid-roll height instead and easing "from" there
  // snapped the switcher back open for one frame, which a trace caught before it was understood.
  // What may still need to move is the bottom edge, if the section grew the panel past its
  // ceiling, and that slide alone is worth animating.
  const displayed = deferred ? { height, bottom: was } : (inFlight ?? memory.shown);
  // A closed panel always re-centres: it is about to be summoned, and it should come back to the
  // middle rather than to wherever the last conversation had pushed it.
  const recentre = at.recentre || memory.view !== at.view || memory.shown === null || !at.open;
  memory.view = at.view;
  const wanted = recentre ? (viewport - height) / 2 : memory.bottom;
  const ceiling = viewport * (1 - MIN_TOP_RATIO) - height;
  const bottom = Math.max(0, Math.min(wanted, ceiling));
  const next: Geometry = { height, bottom };
  memory.bottom = bottom;
  element.style.bottom = `${Math.round(bottom)}px`;
  memory.shown = next;
  if (!at.open || displayed === null || settled(displayed, next)) {
    // Closed, first measurement, or nothing moved: keep the geometry for next time, animate
    // nothing. Measuring while closed is what lets a reopen animate from a real height.
    return;
  }
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return;
  }
  memory.running = element.animate(
    [frame(displayed.height, displayed.bottom), frame(next.height, next.bottom)],
    { duration: DURATION_MS, easing: EASING },
  );
}

/**
 * Own `ref`'s vertical geometry: how tall the panel is and how far off the bottom it sits.
 *
 * Runs on every render (no dependency list on purpose): the trigger is not one piece of state but
 * any DOM change that resized the element. `useLayoutEffect` reads the new geometry after the DOM
 * is updated and before the browser paints, so the animation starts from what the eye last saw
 * rather than from the finished layout.
 *
 * `view` names what the panel is showing; when it changes, the panel re-centres on the way. Pass
 * something that also distinguishes one chat from another, so opening a different chat re-centres
 * too. `open` is false while the panel is closed or minimized, where the size is not what moves:
 * the open/close pop and the corner travel are transforms and own that motion themselves. Under
 * `prefers-reduced-motion` nothing is scheduled at all.
 */
export function usePanelMotion(
  ref: RefObject<HTMLElement | null>,
  open: boolean,
  view: string,
): void {
  const memory = useRef<Memory>({
    shown: null,
    running: null,
    view,
    bottom: 0,
    deferred: false,
  });

  useLayoutEffect(() => {
    place(ref.current, memory.current, { open, view, recentre: false });
  });

  useEffect(() => {
    // The centred position is a fraction of the viewport, so a resized window is a re-centre.
    const onResize = () => place(ref.current, memory.current, { open, view, recentre: true });
    // A section that finished rolling open changed no state, so this is the only word the panel
    // gets that it is taller now and may have grown past its ceiling.
    const onMorphEnd = () => place(ref.current, memory.current, { open, view, recentre: false });
    const element = ref.current;
    window.addEventListener("resize", onResize);
    element?.addEventListener(MORPH_END_EVENT, onMorphEnd);
    return () => {
      window.removeEventListener("resize", onResize);
      element?.removeEventListener(MORPH_END_EVENT, onMorphEnd);
    };
  }, [ref, open, view]);
}
