// The arithmetic behind the panel's vertical motion: where its edges belong, and how long a move
// between two geometries should take. Pure, so the numbers can be reasoned about and tested without
// a DOM; `panelPlacement` is the adapter that measures elements and plays the animations.

import { MIN_DELTA_PX } from "./morph";

// How long a move takes scales with how far it actually goes, at one constant pace, between a floor
// and a ceiling. A single fixed duration is what made streaming feel broken: every token re-renders
// the panel, each render cancels the running ease and starts a fresh one from the in-flight height,
// so a 380ms ease restarted every ~55ms never converged. Traced in a browser at 60Hz: the content
// grew in 22px steps and the panel's top edge crawled about 6px per 200ms behind it, a whole line of
// text in arrears for the length of the reply.
//
// Pacing alone does not stop the restarting, and measurement is the only way to know that: at the
// floor below, a 23px line of growth still started four eases 55ms apart and settled 285ms after the
// text. What the floor is worth is only true alongside `place` resuming a move it has not
// redirected, which is what holds the landing still: one line of growth, one 120ms move, however
// many tokens arrive while it runs.
const MIN_DURATION_MS = 120;
/** The ceiling on a move, exported because the outgoing view's fade in `Panel` is timed to outlast
 *  every resize, which is to say timed to exactly this: restating the number there would let the
 *  fade and the longest morph drift apart with nothing to catch it. */
export const MAX_DURATION_MS = 380;

/** The travel that earns the full duration. Measured, not chosen: the longest move the panel makes
 *  is a full-height chat to the console, which at a 900px viewport slides its top edge 243px (from
 *  `12vh` above a 684px panel to the centre of a 198px one). Rounded down so that move earns the
 *  whole 380ms rather than stopping just short of it, and so every taller viewport does too. */
const FULL_TRAVEL_PX = 240;

/** The tallest the panel may grow, as a fraction of the viewport. Owned here rather than in CSS
 *  because the ceiling below is derived from it and the two must not drift apart. */
const MAX_HEIGHT_RATIO = 0.76;

/** The clear space kept above the panel, as a fraction of the viewport. Derived so that a panel at
 *  full height is EXACTLY centred: growth pushes the top edge up until it reaches this ceiling,
 *  and past that the panel grows downward instead, ending centred rather than jammed at the top. */
const MIN_TOP_RATIO = (1 - MAX_HEIGHT_RATIO) / 2;

export interface Geometry {
  readonly height: number;
  /** Distance from the bottom of the viewport to the panel's bottom edge, in px. */
  readonly bottom: number;
}

export function frame(height: number, bottom: number): Keyframe {
  return { height: `${height}px`, bottom: `${bottom}px` };
}

export function settled(from: Geometry, to: Geometry): boolean {
  return (
    Math.abs(to.height - from.height) < MIN_DELTA_PX &&
    Math.abs(to.bottom - from.bottom) < MIN_DELTA_PX
  );
}

/**
 * The tallest the panel may be in this viewport. Written to the element as `max-height`, and also
 * the cap on any PREDICTED height: a prediction above it is a height the panel cannot reach, and
 * placing the panel for one ran it off the bottom of the screen (see `rideAlong`).
 *
 * Whole pixels, because this number is written to the DOM and then reasoned about afterwards, and
 * the two have to be the same number. Left fractional they were not: `panelPlacement` rounded it on
 * the way out to `max-height` while `rideAlong` capped its prediction at the raw value, so at a
 * viewport where the ratio does not divide evenly the panel stood at one ceiling and was placed for
 * another 0.2px taller. That is under `MIN_DELTA_PX`, so nothing animated it, but the bottom edge is
 * written rounded and 0.2px is enough to cross a rounding boundary. Traced at 60Hz at 640x720 with
 * the reminder stack up, so the panel sat at its ceiling: every roll of a section inside it, a
 * Thoughts trace or the chat switcher alike, began with `bottom` stepping 87 to 86 in one frame with
 * nothing easing it, and stepped back the frame the roll ended. One pixel, twice per roll, on a box
 * with a border and a shadow to catch the eye at its edge.
 */
export function maxHeight(viewport: number): number {
  return Math.round(viewport * MAX_HEIGHT_RATIO);
}

/** The bottom edge that puts a panel of this height in the true middle of the viewport. */
export function centred(viewport: number, height: number): number {
  return (viewport - height) / 2;
}

/**
 * The pinned edge with the ceiling's say applied: how far off the viewport floor a panel this tall
 * may actually sit. The clamp is applied on the way out to the DOM and never written back into
 * memory, so a panel pushed down by its own growth returns to the edge it was pinned to as soon as
 * it shrinks again, and a grow-then-shrink round trip is exactly reversible.
 */
export function clamped(pinned: number, viewport: number, height: number): number {
  return Math.max(0, Math.min(pinned, viewport * (1 - MIN_TOP_RATIO) - height));
}

/**
 * How long this move should take: how far the further-travelling of the panel's two edges goes, at
 * a fixed pace, clamped at both ends. The top edge is `bottom + height` off the viewport floor, so
 * a pure growth moves only that one and a re-centring moves both.
 */
export function durationOf(from: Geometry, to: Geometry): number {
  const travel = Math.max(
    Math.abs(to.bottom - from.bottom),
    Math.abs(to.bottom + to.height - (from.bottom + from.height)),
  );
  const paced = (MAX_DURATION_MS * travel) / FULL_TRAVEL_PX;
  return Math.min(MAX_DURATION_MS, Math.max(MIN_DURATION_MS, paced));
}
