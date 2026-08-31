// The arithmetic behind the panel's vertical motion: where its edges belong, and how long a move
// between two geometries takes. Pure, so `panelPlacement` can be the part that touches the DOM.

import { MIN_DELTA_PX } from "./morph";

// A move takes as long as its distance at one constant pace, between this floor and the ceiling
// below. A single fixed duration made streaming look broken: every token re-renders the panel and
// each render restarts the ease, so a 380ms ease restarted every 55ms never finished.
const MIN_DURATION_MS = 120;
/** The ceiling on a move, exported because the outgoing view's fade in `Panel` is timed to outlast
 *  every resize, which is to say timed to exactly this: restating the number there would let the
 *  fade and the longest morph drift apart with nothing to catch it. */
export const MAX_DURATION_MS = 380;

/** The distance that gets the full duration. Measured, not chosen: the longest move the panel
 *  makes is a full-height chat to the console, which at a 900px viewport slides its top edge 243px.
 *  Rounded down, so that move gets the whole 380ms and every taller viewport does too. */
const FULL_TRAVEL_PX = 240;

/** The clear space kept above the panel, as a fraction of the viewport, so a tall conversation
 *  never runs up against the monitor's bezel. It is the only bound on growth: at the ceiling the
 *  panel stops getting taller and the history scrolls instead. */
const MIN_TOP_RATIO = 0.12;

export interface Geometry {
  readonly height: number;
  /** Distance from the bottom of the viewport to the panel's bottom edge, in px. */
  readonly bottom: number;
}

/** One end of a move, as a keyframe. The ceiling travels with it, because `max-height` clamps an
 *  animated height exactly as it clamps a laid-out one, and both ends interpolate under one easing,
 *  so the cap is never tighter than the height it is clamping. */
export function frame(height: number, bottom: number, ceiling: number): Keyframe {
  return { height: `${height}px`, bottom: `${bottom}px`, maxHeight: `${ceiling}px` };
}

export function settled(from: Geometry, to: Geometry): boolean {
  return (
    Math.abs(to.height - from.height) < MIN_DELTA_PX &&
    Math.abs(to.bottom - from.bottom) < MIN_DELTA_PX
  );
}

/** The tallest the panel may be from the edge it is held to: everything between that edge and the
 *  clear space at the top, which is what makes growth purely upward. Whole pixels, because this is
 *  written to the DOM and then reasoned about, and a 0.2px difference stepped the bottom edge. */
export function maxHeight(viewport: number, bottom: number): number {
  return Math.round(viewport * (1 - MIN_TOP_RATIO) - Math.max(0, bottom));
}

/** The tallest a panel can be before it is placed, which is the tallest a centred one can be. A
 *  centred panel of height h sits at `(viewport - h) / 2`, so the ceiling above allows
 *  `0.88v - (v - h)/2`, and solving for h gives `h <= 0.76v`. */
export function openHeight(viewport: number): number {
  return Math.round(viewport * (1 - 2 * MIN_TOP_RATIO));
}

/** The bottom edge that puts a panel of this height in the true middle of the viewport. */
export function centred(viewport: number, height: number): number {
  return (viewport - height) / 2;
}

/** The bottom edge a view of more than one shape arrives on: the one that puts its top where its
 *  tallest shape would have put it. Worked out in full rather than as an adjustment, because the
 *  tallest shape may not fit above that edge at all. */
export function arrivalBottom(
  viewport: number,
  edge: number,
  height: number,
  slack: number,
): number {
  const clearTop = viewport - maxHeight(viewport, 0);
  const top = Math.max(clearTop, viewport - edge - (height + slack));
  return viewport - top - height;
}

/** The `pinned` edge as the DOM may have it: on screen, and nothing more. The ceiling is applied
 *  to the height instead, because pushing the bottom edge down to make room for a taller panel is
 *  the downward growth that is not wanted. */
export function clamped(pinned: number): number {
  return Math.max(0, pinned);
}

/** How long this move takes: how far the further-travelling of the panel's two edges goes, at a
 *  fixed pace, clamped at both ends. The top edge is `bottom + height` off the viewport floor, so
 *  growth moves one edge and a re-centring moves both. */
export function durationOf(from: Geometry, to: Geometry): number {
  const travel = Math.max(
    Math.abs(to.bottom - from.bottom),
    Math.abs(to.bottom + to.height - (from.bottom + from.height)),
  );
  const paced = (MAX_DURATION_MS * travel) / FULL_TRAVEL_PX;
  return Math.min(MAX_DURATION_MS, Math.max(MIN_DURATION_MS, paced));
}
