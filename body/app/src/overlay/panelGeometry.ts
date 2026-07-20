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

/** The clear space kept above the panel, as a fraction of the viewport: how far its top edge stays
 *  off the top of the screen, so a tall conversation never runs up against the monitor's bezel.
 *
 *  It is the ONLY bound on growth. There used to be a second one, a flat maximum height, and the two
 *  together meant a panel that had climbed to this ceiling kept growing DOWNWARD to reach that
 *  height, walking its bottom edge back down the screen with the composer on it. Growth is upward or
 *  it does not happen: at the ceiling the panel simply stops getting taller and the history scrolls,
 *  which is what the history is for. */
const MIN_TOP_RATIO = 0.12;

export interface Geometry {
  readonly height: number;
  /** Distance from the bottom of the viewport to the panel's bottom edge, in px. */
  readonly bottom: number;
}

/**
 * One end of a move, as a keyframe.
 *
 * The CEILING travels with it, which is not decoration: `max-height` clamps an animated `height`
 * exactly as it clamps a laid-out one, and the ceiling belongs to the edge the panel is going to, so
 * it is already the destination's while the panel is still at the origin's size. Traced at 60Hz at
 * 640x720, opening the console from a full-height chat: the ease was written 450 to 347, and the
 * panel stood at 351 one frame after the click and eased the last 4px from there. What the eye gets
 * is the whole shrink in a single frame followed by an animation of nothing, which is the "it pops
 * and then animates" this exists to stop. Ridden along, the cap is never tighter than the height it
 * is clamping: both ends interpolate under one easing, so a from-cap at or above the from-height
 * keeps the cap above the height for every frame between.
 */
export function frame(height: number, bottom: number, ceiling: number): Keyframe {
  return { height: `${height}px`, bottom: `${bottom}px`, maxHeight: `${ceiling}px` };
}

export function settled(from: Geometry, to: Geometry): boolean {
  return (
    Math.abs(to.height - from.height) < MIN_DELTA_PX &&
    Math.abs(to.bottom - from.bottom) < MIN_DELTA_PX
  );
}

/**
 * The tallest the panel may be from the edge it is pinned to: everything between that edge and the
 * clear space kept at the top. It therefore depends on where the panel currently sits, which is what
 * makes growth purely upward. Written to the element as `max-height`, and also
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
export function maxHeight(viewport: number, bottom: number): number {
  return Math.round(viewport * (1 - MIN_TOP_RATIO) - Math.max(0, bottom));
}

/** The tallest a panel can be before it is placed, which is the tallest a CENTRED one can be. A
 *  centred panel of height h sits at `(viewport - h) / 2`, so the ceiling above allows
 *  `0.88v - (v - h)/2`, and solving `h <= that` gives `h <= 0.76v`. Used to measure the natural
 *  height before the bottom edge is known, which is the order the two have to be decided in: the
 *  cap depends on the edge and the edge depends on the height. Measuring under the loosest cap
 *  either could allow, deciding the edge, then applying the real cap gets both right in one pass. */
export function openHeight(viewport: number): number {
  return Math.round(viewport * (1 - 2 * MIN_TOP_RATIO));
}

/** The bottom edge that puts a panel of this height in the true middle of the viewport. */
export function centred(viewport: number, height: number): number {
  return (viewport - height) / 2;
}

/**
 * The pinned edge as the DOM may have it: on screen, and nothing more. The ceiling is no longer
 * applied here, because it is applied to the HEIGHT instead (`maxHeight`); pushing the bottom edge
 * down to make room for a taller panel is exactly the downward growth that is not wanted.
 */
export function clamped(pinned: number): number {
  return Math.max(0, pinned);
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
