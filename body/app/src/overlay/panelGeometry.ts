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

/**
 * The clear space kept above the panel, as a fraction of the viewport: how far its top edge stays
 * off the top of the screen, so a tall conversation never runs up against the monitor's bezel.
 */
const MIN_TOP_RATIO = 0.12;

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
 * The tallest the panel may be from the edge it is pinned to: everything between that edge and the
 * clear space kept at the top.
 */
export function maxHeight(viewport: number, bottom: number): number {
  return Math.round(viewport * (1 - MIN_TOP_RATIO) - Math.max(0, bottom));
}

/** The tallest a panel can be before it is placed, which is the tallest a CENTRED one can be. */
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
