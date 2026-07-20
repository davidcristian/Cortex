// The arithmetic behind the panel's vertical motion: where its edges belong, and how long a move
// between two geometries should take. Pure, so the numbers can be reasoned about and tested without
// a DOM; `panelPlacement` is the adapter that measures elements and plays the animations.

import { MIN_DELTA_PX } from "./morph";

const MIN_DURATION_MS = 120;
/** The ceiling on a move, exported because the outgoing view's fade in `Panel` is timed to outlast
 *  every resize, which is to say timed to exactly this: restating the number there would let the
 *  fade and the longest morph drift apart with nothing to catch it. */
export const MAX_DURATION_MS = 380;

/** The travel that earns the full duration. */
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
 * may actually sit.
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
